# src/agents/research.py
from __future__ import annotations

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# storage
DATA_DIR = Path("data/research")
DATA_DIR.mkdir(parents=True, exist_ok=True)
ERROR_LOG = DATA_DIR / "_last_error.log"

# expected 5 subscores
EXPECTED_KEYS = [
    "research_innovation",
    "econ_evidence",
    "sustainability_esg",
    "regulatory_outlook",
    "thematic_alignment",
]


def _write_error(obj: Dict[str, Any]) -> None:
    """write last error to disk for inspection"""
    try:
        ERROR_LOG.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    except Exception:
        pass


class ResearchAgent:
    """
    Weekly, slow, research-focused agent.
    - holt 1x/Woche eine akademisch/regulatorisch begründete Einschätzung pro Asset
    - speichert lokal
    - wenn Datei frisch: wiederverwenden
    - wenn LLM/Quota/Parsing failt: inputs_fresh = False
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_age_days: int = 7,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        # env override > fallback
        self.model = model or os.getenv("RESEARCH_MODEL", "gpt-5")
        self.max_age_days = max_age_days

    def run(self, universe: List[str], asof: datetime) -> List[Dict[str, Any]]:
        # try to load last research file
        latest = self._load_latest()
        if latest and self._is_fresh(latest["ts"], asof):
            return [self._to_vote(pair, latest["data"].get(self._to_asset(pair)), asof) for pair in universe]

        # else: fetch fresh from LLM, one asset after another
        fresh: Dict[str, Any] = {}
        for pair in universe:
            asset = self._to_asset(pair)
            resp = self._query_llm(asset)
            if resp is not None:
                fresh[asset] = resp

        # save to disk for the next 7 days
        self._save(asof, fresh)

        # convert to votes
        return [self._to_vote(pair, fresh.get(self._to_asset(pair)), asof) for pair in universe]

    # ------------------------------------------------------------------

    def _query_llm(self, asset: str) -> Optional[Dict[str, Any]]:
        """call OpenAI responses API with a research-only prompt"""
        if not self.api_key:
            _write_error({"error": "missing OPENAI_API_KEY"})
            return None

        url = "https://api.openai.com/v1/responses"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # prompt: research, not news
        prompt = (
            "You are a research-focused crypto analyst with a trading background.\n"
            "Your task is to summarize medium- to long-term signals for ONE asset, based ONLY on research-like sources:\n"
            "- academic / peer-reviewed / preprints (arXiv, SSRN, IEEE, ACM),\n"
            "- econometric or market microstructure studies (volatility clustering, spillovers, inefficiencies),\n"
            "- sustainability / ESG assessments of consensus mechanisms (energy use, PoW vs. PoS),\n"
            "- regulatory publications and guidance (SEC, CFTC, ESMA, EBA, FATF, MiCA).\n"
            "IGNORE daily news, blogs, exchange announcements, social media, or price headlines.\n"
            "Return ONLY this JSON:\n"
            "{\n"
            f'  "asset": "{asset}",\n'
            '  "scores": {\n'
            '    "research_innovation": number in [-1,1],\n'
            '    "econ_evidence": number in [-1,1],\n'
            '    "sustainability_esg": number in [-1,1],\n'
            '    "regulatory_outlook": number in [-1,1],\n'
            '    "thematic_alignment": number in [-1,1]\n'
            "  },\n"
            '  "notes": "max 60 words. cite concrete papers or institutions if possible."\n'
            "}\n"
            "Rules:\n"
            "- If evidence is mixed, use values near 0.\n"
            "- If no evidence is found for a field, set it to 0.\n"
            "- All numbers MUST be floats in [-1,1].\n"
            "- Do not add extra fields.\n"
        )

        payload = {
            "model": self.model,
            "input": prompt,
            "temperature": 0.2,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=40)
        except Exception as e:
            _write_error({"error": "request_failed", "exception": str(e)})
            return None

        if resp.status_code != 200:
            _write_error(
                {
                    "error": "http_error",
                    "status": resp.status_code,
                    "text": resp.text,
                }
            )
            return None

        try:
            data = resp.json()
        except Exception as e:
            _write_error({"error": "json_parse_error", "text": resp.text, "exception": str(e)})
            return None

        # try responses output structure
        text = None
        if "output" in data and isinstance(data["output"], list) and data["output"]:
            first = data["output"][0]
            if isinstance(first, dict):
                content = first.get("content")
                if isinstance(content, list) and content:
                    maybe_text = content[0].get("text")
                    if isinstance(maybe_text, str):
                        text = maybe_text

        # fallback to chat-like
        if text is None and "choices" in data:
            text = data["choices"][0]["message"]["content"]

        if text is None:
            _write_error({"error": "no_text_in_response", "data": data})
            return None

        try:
            parsed = json.loads(text)
            return parsed
        except Exception as e:
            _write_error({"error": "content_not_json", "content": text, "exception": str(e)})
            return None

    # ------------------------------------------------------------------

    def _to_vote(self, pair: str, entry: Optional[Dict[str, Any]], asof: datetime) -> Dict[str, Any]:
        """convert stored JSON to agent vote for consensus"""
        if entry is None:
            return {
                "pair": pair,
                "agent": "research",
                "score": 0.0,
                "confidence": 0.0,
                "inputs_fresh": False,
                "asof": asof.isoformat(),
                "explanation": "research: no data",
            }

        scores = entry.get("scores", {})
        vals: List[float] = []
        valid = 0
        for key in EXPECTED_KEYS:
            v = scores.get(key)
            if isinstance(v, (int, float)):
                vv = max(-1.0, min(1.0, float(v)))
                vals.append(vv)
                valid += 1

        final_score = sum(vals) / len(vals) if vals else 0.0
        confidence = valid / len(EXPECTED_KEYS)

        return {
            "pair": pair,
            "agent": "research",
            "score": round(final_score, 3),
            "confidence": round(confidence, 3),
            "inputs_fresh": True,
            "asof": asof.isoformat(),
            "explanation": f"research: {valid}/{len(EXPECTED_KEYS)} scores for {pair}",
        }

    # ------------------------------------------------------------------

    def _save(self, asof: datetime, data: Dict[str, Any]) -> None:
        ts = int(asof.replace(tzinfo=timezone.utc).timestamp())
        obj = {"ts": ts, "data": data}
        fname = DATA_DIR / f"research_{asof.date().isoformat()}.json"
        try:
            fname.write_text(json.dumps(obj), encoding="utf-8")
        except Exception:
            pass

    def _load_latest(self) -> Optional[Dict[str, Any]]:
        files = sorted(DATA_DIR.glob("research_*.json"), reverse=True)
        if not files:
            return None
        try:
            return json.loads(files[0].read_text(encoding="utf-8"))
        except Exception:
            return None

    def _is_fresh(self, ts: int, asof: datetime) -> bool:
        age = asof.replace(tzinfo=timezone.utc).timestamp() - ts
        return age <= self.max_age_days * 86400

    @staticmethod
    def _to_asset(pair: str) -> str:
        up = pair.upper()
        for suff in ("USDT", "USD", "BUSD", "EUR"):
            if up.endswith(suff):
                return up[: -len(suff)]
        return up
