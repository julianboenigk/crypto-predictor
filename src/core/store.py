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
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        for stmt in SCHEMA.strip().split(";"):
            s = stmt.strip()
            if s:
                db.execute(s)
