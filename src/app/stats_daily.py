from __future__ import annotations
import json, os, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict, Counter
from src.core.notify import send_telegram

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "data" / "runs.log"

def _load():
    if not RUNS.exists(): return []
    out=[]
    with RUNS.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out

def main():
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)

    runs = _load()
    recs=[]  # (t, pair, decision, score)
    for r in runs:
        try:
            t = datetime.fromisoformat(r["run_at"])
        except Exception:
            continue
        if t < since: continue
        for res in r.get("results", []):
            recs.append((t, res.get("pair","?"), res.get("decision","HOLD").upper(), float(res.get("score",0.0))))

    if not recs:
        send_telegram("Daily stats: no runs in the last 24h.", parse_mode="Markdown")
        return

    by_pair = defaultdict(list)
    for t,p,d,s in recs:
        by_pair[p].append((d,s))

    lines = ["*Daily Signal Summary (last 24h)*"]
    total = Counter()
    for pair, lst in sorted(by_pair.items()):
        c = Counter(d for d,_ in lst)
        avg = sum(s for _,s in lst)/len(lst)
        lines.append(f"- {pair}: LONG {c['LONG']}, SHORT {c['SHORT']}, HOLD {c['HOLD']}, avg score {avg:+.2f}")
        total.update(c)

    lines.append("")
    lines.append(f"Totals: LONG {total['LONG']}, SHORT {total['SHORT']}, HOLD {total['HOLD']}")
    lines.append(f"_Generated at {now.strftime('%Y-%m-%d %H:%M UTC')}_")

    send_telegram("\n".join(lines), parse_mode="Markdown")

if __name__ == "__main__":
    main()
