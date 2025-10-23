import requests, time

_URL = "https://api.alternative.me/fng/?limit=1&format=json"
_cache = {"t": 0, "v": None}

def fetch_fng() -> dict:
    # cache 10 minutes
    if time.time() - _cache["t"] < 600 and _cache["v"] is not None:
        return _cache["v"]
    try:
        r = requests.get(_URL, timeout=15)
        r.raise_for_status()
        item = r.json()["data"][0]
        v = {
            "value": int(item["value"]),
            "classification": item["value_classification"],  # e.g., "Greed"
            "timestamp": item["timestamp"]
        }
        _cache["t"] = time.time()
        _cache["v"] = v
        return v
    except Exception:
        return {"value": None, "classification": "n/a", "timestamp": None}
