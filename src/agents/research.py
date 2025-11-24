# src/agents/research.py
from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from src.core.llm import simple_completion


DATA_DIR = Path("data/research")
DATA_DIR.mkdir(parents=True, exist_ok=True)


class ResearchAgent:
    """
    Research Agent:
    - ruft für jedes Asset genau EINEN LLM-Call ab
    - nutzt ONLY akademische / regulatorische / langfristige Quellen
    - output: score pro Dimension [-1,1] + kurze Notes
    """

    def __init__(self) -> None:
        # ENV override möglich
        self.model = os.getenv("OPENAI_MODEL_RESEARCH", "gpt-4.1-mini")

    def _build_prompt(self, asset: str) -> str:
        """
        Baut den Prompt für EIN Asset.
        """
        prompt = (
            "You are a research-focused crypto analyst with academic and quantitative background.\n"
            "Evaluate ONE crypto asset based strictly on medium- to long-term, evidence-based sources:\n"
            "- academic / peer-reviewed / preprints (arXiv, SSRN, IEEE, ACM),\n"
            "- econometric or market microstructure studies (volatility clustering, spillovers, inefficiencies),\n"
            "- sustainability / ESG assessments of consensus mechanisms (energy usage, PoW vs. PoS),\n"
            "- regulatory publications and guidance (SEC, CFTC, ESMA, EBA, FATF, MiCA).\n"
            "\n"
            "IGNORE: daily news, blogs, exchange announcements, social media, influencers, price headlines.\n"
            "Your job is to rate the asset in FIVE dimensions — all in [-1,1]:\n"
            "- research_innovation\n"
            "- econ_evidence\n"
            "- sustainability_esg\n"
            "- regulatory_outlook\n"
            "- thematic_alignment\n"
            "\n"
            "Rules:\n"
            "- If evidence is mixed: use values near 0.\n"
            "- If no evidence exists: score = 0.\n"
            "- You MUST cite 2–3 concrete academic or regulatory sources (arXiv/SSRN/IEEE IDs or institutions).\n"
            "- Do NOT invent fake papers.\n"
            "- Do NOT add extra fields.\n"
            "- Answer ONLY with valid JSON.\n"
            "\n"
            "Return exactly this JSON:\n"
            "{\n"
            f'  \"asset\": \"{asset}\",\n'
            "  \"scores\": {\n"
            "    \"research_innovation\": <float>,\n"
            "    \"econ_evidence\": <float>,\n"
            "    \"sustainability_esg\": <float>,\n"
            "    \"regulatory_outlook\": <float>,\n"
            "    \"thematic_alignment\": <float>\n"
            "  },\n"
            "  \"notes\": \"max 80 words, concise, include 2–3 concrete sources (arXiv/SSRN/IEEE/Regulators).\"\n"
            "}\n"
        )
        return prompt

    def _call_llm(self, asset: str) -> Dict[str, Any]:
        """
        Führt einen LLM-Call aus und gibt das JSON zurück.
        """
        prompt = self._build_prompt(asset)
        text = simple_completion(
            system_prompt="You are an academic crypto research agent.",
            user_prompt=prompt,
            model_env_var="OPENAI_MODEL_RESEARCH",
            default_model=self.model,
            max_tokens=800,
            context="research",
        )

        # JSON extrahieren
        try:
            obj = json.loads(text)
            return obj
        except Exception:
            return {
                "asset": asset,
                "scores": {
                    "research_innovation": 0.0,
                    "econ_evidence": 0.0,
                    "sustainability_esg": 0.0,
                    "regulatory_outlook": 0.0,
                    "thematic_alignment": 0.0,
                },
                "notes": "Invalid JSON returned by model.",
            }

    def run(self, assets: List[str], asof: datetime) -> List[Dict[str, Any]]:
        """
        Hauptmethode für das gesamte System.
        """
        results: List[Dict[str, Any]] = []

        for asset in assets:
            obj = self._call_llm(asset)
            scores = obj.get("scores", {})

            # Normalisieren (Safety)
            normalized_scores = {}
            for k in [
                "research_innovation",
                "econ_evidence",
                "sustainability_esg",
                "regulatory_outlook",
                "thematic_alignment",
            ]:
                try:
                    v = float(scores.get(k, 0.0))
                except Exception:
                    v = 0.0
                normalized_scores[k] = max(-1.0, min(1.0, v))

            results.append(
                {
                    "pair": f"{asset}USDT",
                    "agent": "research",
                    "score": sum(normalized_scores.values()) / 5.0,
                    "confidence": len(normalized_scores) / 5.0,
                    "inputs_fresh": True,
                    "breakdown": list(normalized_scores.items()),
                    "timestamp": asof.isoformat(),
                }
            )

        # speichern
        outfile = DATA_DIR / f"research_{asof.strftime('%Y-%m-%d')}.json"
        outfile.write_text(json.dumps(results, indent=2), encoding="utf-8")

        return results
