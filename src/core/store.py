from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("data/signals.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_utc TEXT NOT NULL,
  finished_utc TEXT,
  status TEXT NOT NULL,
  notes TEXT
);
CREATE TABLE IF NOT EXISTS agent_outputs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  pair TEXT NOT NULL,
  agent TEXT NOT NULL,
  score REAL NOT NULL,
  confidence REAL NOT NULL,
  explanation TEXT NOT NULL,
  inputs_fresh INTEGER NOT NULL,
  latency_ms INTEGER NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);
CREATE TABLE IF NOT EXISTS signals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  pair TEXT NOT NULL,
  consensus REAL NOT NULL,
  decision TEXT NOT NULL,
  reason TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(id)
);
"""


def init_db() -> None:
    """Initialize SQLite database and create schema if missing."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        for stmt in SCHEMA.strip().split(";"):
            s = stmt.strip()
            if s:
                db.execute(s)


# ---------- Helpers for run logging and persistence ----------

def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def start_run(ts_utc: str, notes: str = "") -> int:
    """Insert a new run record and return its ID."""
    with _conn() as db:
        cur = db.execute(
            "INSERT INTO runs(started_utc,status,notes) VALUES(?, ?, ?)",
            (ts_utc, "running", notes),
        )
        run_id = cur.lastrowid
        assert run_id is not None, "sqlite returned None lastrowid"
        return int(run_id)


def end_run(run_id: int, ts_utc: str, status: str = "ok", notes: str = "") -> None:
    """Mark a run as finished."""
    with _conn() as db:
        db.execute(
            "UPDATE runs SET finished_utc=?, status=?, notes=? WHERE id=?",
            (ts_utc, status, notes, run_id),
        )


def save_agent_output(
    run_id: int,
    pair: str,
    agent: str,
    score: float,
    confidence: float,
    explanation: str,
    inputs_fresh: bool,
    latency_ms: int,
) -> None:
    """Store one agent's output in the database."""
    with _conn() as db:
        db.execute(
            "INSERT INTO agent_outputs(run_id,pair,agent,score,confidence,explanation,inputs_fresh,latency_ms) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (
                run_id,
                pair,
                agent,
                float(score),
                float(confidence),
                explanation,
                int(inputs_fresh),
                int(latency_ms),
            ),
        )


def save_signal(run_id: int, pair: str, consensus: float, decision: str, reason: str) -> None:
    """Store the consensus signal."""
    with _conn() as db:
        db.execute(
            "INSERT INTO signals(run_id,pair,consensus,decision,reason) VALUES(?,?,?,?,?)",
            (run_id, pair, float(consensus), decision, reason),
        )
