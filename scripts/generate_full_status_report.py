#!/usr/bin/env python
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "reports" / "Crypto_Predictor_Full_Status_Report.pdf"


def run_cmd(cmd: List[str]) -> str:
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def get_git_branches() -> str:
    # local + remote branches
    branches = run_cmd(["git", "branch", "--all"])
    if not branches:
        return "(no git branches found or git not available)"
    return branches


def get_git_status() -> str:
    status = run_cmd(["git", "status", "--short", "--branch"])
    if not status:
        return "(no git status available)"
    return status


def scan_scripts() -> Dict[str, List[str]]:
    """
    Scannt src/ und scripts/ und gruppiert Dateien nach Top-Level-Verzeichnis.
    Beispiele:
      src/app/main.py -> app: [main.py]
      src/agents/technical.py -> agents: [...]
      scripts/heartbeat.sh -> scripts: [...]
    """
    result: Dict[str, List[str]] = {}

    # src/*
    src_dir = ROOT / "src"
    if src_dir.exists():
        for dirpath, dirnames, filenames in os.walk(src_dir):
            rel_dir = Path(dirpath).relative_to(src_dir)
            parts = rel_dir.parts
            top = parts[0] if parts else "src_root"
            for fn in sorted(filenames):
                if fn.startswith("."):
                    continue
                if not (fn.endswith(".py") or fn.endswith(".sh")):
                    continue
                rel_file = Path(dirpath).relative_to(ROOT) / fn
                result.setdefault(top, []).append(str(rel_file))

    # scripts/*
    scripts_dir = ROOT / "scripts"
    if scripts_dir.exists():
        key = "scripts"
        for fn in sorted(os.listdir(scripts_dir)):
            if fn.startswith("."):
                continue
            if not (fn.endswith(".sh") or fn.endswith(".py")):
                continue
            rel_file = Path("scripts") / fn
            result.setdefault(key, []).append(str(rel_file))

    # sort lists
    for k in result:
        result[k] = sorted(result[k])

    return dict(sorted(result.items(), key=lambda kv: kv[0]))


def build_backlog_text() -> str:
    """
    Priorisierter Backlog, textuell.
    """
    return """
7. Backlog — Prioritized by Value Creation
=========================================

HIGH VALUE — Execution & Performance
------------------------------------
1. Paper-trade lifecycle
   - Implement a persistent paper-trade book (SQLite or JSON).
   - Track open positions (pair, side, entry, SL, TP, size, meta).
   - Evaluate SL/TP hits on each new candle and close trades accordingly.
   - Compute PnL per trade (in R and optionally in USD).
   - Aggregate daily/weekly PnL metrics.

2. Real trading readiness (Binance Testnet)
   - Integrate Binance Testnet via ccxt.
   - Map signals (LONG/SHORT) + order levels to testnet orders.
   - Simulate basic liquidity and slippage constraints.
   - Add global risk guard (max concurrent trades, max risk per day).

3. Adaptive agent weighting v2
   - Evaluate each agent’s historical predictive power over the last N trades.
   - Increase weights for agents that contribute to profitable trades.
   - Decrease weights for agents that frequently co-occur with losing trades.
   - Persist weight history for later analysis.

4. Threshold tuning engine
   - Automate R:R and threshold sweeps over historical runs.log.
   - Find per-pair optimal thresholds for LONG/SHORT decisions.
   - Multi-objective evaluation: maximize PnL while controlling drawdown and trade frequency.
   - Store results in a configuration file (e.g., thresholds.yaml) per pair.

MEDIUM VALUE — Analytics & Transparency
---------------------------------------
5. Weekly PDF performance report
   - Combine daily backtest summaries into a weekly report.
   - Include equity curves for 7/30/90-day windows.
   - Add agent performance charts.
   - Distribute via Telegram and store in data/reports.

6. Agent contribution analytics
   - For each trade, log the individual agent scores and confidences.
   - Build per-agent hit-rate and PnL statistics.
   - Visualize agent importance over time.

7. Risk metrics & benchmarks
   - Compute Sharpe ratio, Sortino ratio, and maximum drawdown.
   - Compare the system against simple benchmarks (Buy & Hold BTC, etc.).
   - Add these metrics to daily and weekly reports.

LOWER VALUE — Ecosystem & UX
----------------------------
8. Slack/Webhook integrations
   - Mirror Telegram alerts to Slack or generic webhooks.
   - Allow external systems to consume signals programmatically.

9. Lightweight Web Dashboard
   - Small Flask/FastAPI app serving read-only charts and statistics.
   - Simple HTML pages with equity curves, winrates, and trade tables.

10. Research Agent v2
   - Use embeddings and a vector store to retrieve relevant academic papers.
   - Provide traceable references in the research notes.
   - Periodic (e.g., weekly) refresh of the research knowledge base.
"""


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]

    story = []

    def add_para(text: str, style=normal, space_after: float = 0.3):
        story.append(Paragraph(text, style))
        story.append(Spacer(1, space_after * cm))

    # 1) Title
    add_para("Crypto Predictor — Full Ultra-Detailed Status Report", h1, 0.5)
    add_para(
        "This report is generated directly from the local git repository and file tree. "
        "It summarizes architecture, scripts, branches, automation, and the prioritized backlog.",
        normal,
        0.5,
    )
    story.append(PageBreak())

    # 2) Git status and branches
    add_para("1. Git Repository Status", h1, 0.3)

    status = get_git_status()
    add_para("1.1 Current git status", h2, 0.2)
    add_para("<pre>%s</pre>" % status.replace("\n", "<br/>"), normal, 0.5)

    branches = get_git_branches()
    add_para("1.2 Branches (local + remote)", h2, 0.2)
    add_para("<pre>%s</pre>" % branches.replace("\n", "<br/>"), normal, 0.5)

    story.append(PageBreak())

    # 3) Architecture summary (static text, but aligned mit deinem Setup)
    add_para("2. System Architecture Overview", h1, 0.3)
    arch_text = """
The Crypto Predictor follows a layered, multi-agent architecture:

- Data Layer
  - Fetches OHLCV data from Binance.
  - Pulls news and sentiment from CryptoNewsAPI.
  - Caches responses to reduce API load.

- Agent Layer
  - Technical Agent: EMA200, RSI14, ATR-based risk.
  - Sentiment Agent: Daily sentiment based on CryptoNewsAPI statistics.
  - News Agent: Trend and topical intensity around each asset.
  - Research Agent: Academic and macro research summarization (5 subscores per asset).

- Consensus Layer
  - Merges individual agent scores into a single consensus score S in [-1, 1].
  - Uses dynamic agent weights derived from recent run history.
  - Fails closed when inputs are stale or inconsistent.

- Policy Layer
  - Applies decision thresholds (LONG, SHORT, HOLD).
  - Enforces risk filters (volatility, R:R).
  - Configurable via YAML and environment variables.

- Output & Analytics Layer
  - Sends Telegram alerts for strong LONG/SHORT signals.
  - Produces daily backtest snapshots.
  - Generates equity PNG plots and CSV summaries.
  - Maintains logs for reproducible backtests.
"""
    add_para("<pre>%s</pre>" % arch_text.replace("\n", "<br/>"), normal, 0.5)
    story.append(PageBreak())

    # 4) Script inventory (dynamic)
    add_para("3. Script and File Inventory", h1, 0.3)
    inv = scan_scripts()
    for group, files in inv.items():
        add_para(f"3.{group} — {group}", h2, 0.2)
        lines = "\n".join(files)
        add_para("<pre>%s</pre>" % lines.replace("\n", "<br/>"), normal, 0.5)

    story.append(PageBreak())

    # 5) Automation & Cron
    add_para("4. Automation and Cron Jobs", h1, 0.3)
    cron_summary = """
The following cron jobs orchestrate the system:

- Every 15 minutes:
  - Run the main engine with all agents and consensus.
  - Emit LONG/SHORT alerts to Telegram if score exceeds configured thresholds.

- Daily at 09:00:
  - Heartbeat script to verify that the system is alive.

- Daily at 02:30:
  - Cleanup script to rotate logs and purge old temporary data.

- Weekly at 03:10 on Sunday:
  - Backup script to create full snapshots of critical data.

- Daily at 23:55:
  - Backtest snapshot via src.backtest.save_last.

- Daily at 23:58:
  - Telegram report via src.reports.daily_backtest_summary, including text summary and equity curve.

- Daily at 23:59:
  - CSV export via src.reports.backtest_to_csv.

- Daily at 00:00:
  - Equity PNG regeneration via src.reports.plot_equity.
"""
    add_para("<pre>%s</pre>" % cron_summary.replace("\n", "<br/>"), normal, 0.5)
    story.append(PageBreak())

    # 6) Reliability Layer
    add_para("5. Reliability and Observability", h1, 0.3)
    reliability = """
The system implements multiple reliability mechanisms:

- Input freshness checks for OHLCV and external APIs.
- Fail-closed consensus: if any core input is stale or invalid, decision defaults to HOLD.
- Strict logging of each run in data/runs.log for reproducible backtesting.
- Dynamic agent weights based on recent run history (configurable and with fallbacks).
- Timezone normalization for all timestamps and Telegram messages.
- Daily backtest snapshots and summary reports to detect drifts in performance.
"""
    add_para("<pre>%s</pre>" % reliability.replace("\n", "<br/>"), normal, 0.5)
    story.append(PageBreak())

    # 7) Backlog
    add_para("6. Prioritized Backlog", h1, 0.3)
    backlog = build_backlog_text()
    add_para("<pre>%s</pre>" % backlog.replace("\n", "<br/>"), normal, 0.5)

    # Build PDF
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4)
    doc.build(story)

    print(f"Status report written to: {OUTPUT}")


if __name__ == "__main__":
    main()
