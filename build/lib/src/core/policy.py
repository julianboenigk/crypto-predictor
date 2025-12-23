from __future__ import annotations
from typing import Sequence

def freshness_gate(inputs_fresh_flags: Sequence[bool]) -> tuple[bool, str]:
    ok = all(inputs_fresh_flags)
    return ok, "fresh" if ok else "stale inputs"

def rr_gate(r_multiple: float, min_rr: float = 1.5) -> tuple[bool, str]:
    ok = r_multiple >= min_rr
    return ok, f"R:R={r_multiple:.2f}>= {min_rr}" if ok else f"R:R={r_multiple:.2f}<{min_rr}"
