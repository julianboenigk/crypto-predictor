import sys
from pathlib import Path

# Project root = tests/..
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# Ensure deterministic import path for pytest
for p in (ROOT, SRC):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)
