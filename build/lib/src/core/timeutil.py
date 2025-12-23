# src/core/timeutil.py
from __future__ import annotations
import os
from datetime import datetime
import pytz

def now_local():
    tzname = os.getenv("TIMEZONE", "Europe/Berlin")
    try:
        tz = pytz.timezone(tzname)
    except Exception:
        tz = pytz.timezone("Europe/Berlin")
    return datetime.now(tz)

def fmt_local(ts: datetime | None = None) -> str:
    if ts is None:
        ts = now_local()
    return ts.strftime("%Y-%m-%d %H:%M %Z")
