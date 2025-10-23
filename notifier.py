import requests
from datetime import datetime
import pytz
import config

# ----------------------------------------------------------------------
# Telegram send
# ----------------------------------------------------------------------
def send_telegram(text: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=20,
        )
        return r.ok
    except Exception:
        return False

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))

def _to_berlin(ts_str: str) -> str:
    """Convert ISO or naive timestamp → 'DD.MM.YYYY HH:MM CET/CEST'."""
    try:
        tz = pytz.timezone("Europe/Berlin")
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        local = ts.astimezone(tz)
        return local.strftime("%d.%m.%Y %H:%M %Z")
    except Exception:
        return ts_str

# ----------------------------------------------------------------------
# Confidence scoring
# ----------------------------------------------------------------------
def _confidence(s: dict) -> tuple[str, float]:
    rsi = float(s["rsi14"])
    price = float(s["price"])
    ema = float(s["ema200"]) if float(s["ema200"]) != 0 else 1.0
    rr = float(s["rr"])
    exp_ret = float(s["expected_return_pct"])
    side = s["signal"]

    if side == "LONG":
        rsi_dir = max(0.0, rsi - 50.0) / 25.0
    else:
        rsi_dir = max(0.0, 50.0 - rsi) / 25.0
    rsi_score = _clamp(rsi_dir)

    dist_pct = (price / ema - 1.0) * 100.0
    if side == "SHORT":
        dist_pct = -dist_pct
    trend_score = _clamp(dist_pct / 4.0)

    rr_score = _clamp(rr / 2.0)
    exp_score = _clamp(exp_ret / 10.0)

    score = (0.35 * rsi_score) + (0.25 * trend_score) + (0.25 * rr_score) + (0.15 * exp_score)
    if score >= 0.70:
        label = "High"
    elif score >= 0.45:
        label = "Medium"
    else:
        label = "Low"
    return label, round(score, 2)

# ----------------------------------------------------------------------
# Message formatting
# ----------------------------------------------------------------------
def fmt_signal(s: dict, ctx: dict | None = None) -> str:
    fng = (ctx or {}).get("fng", {})
    mood = ""
    if fng and fng.get("value") is not None:
        mood = f"\nMarket mood: {fng['classification']} (Fear & Greed = {fng['value']})"

    conf_label, conf_score = _confidence(s)

    side = s["signal"]
    coin = s["coin_id"].replace("USDT", "")
    direction = "📈 LONG signal" if side == "LONG" else "📉 SHORT signal"

    price = round(float(s["price"]), 4)
    target = round(float(s["target"]), 4)
    stop = round(float(s["stop"]), 4)
    rr = round(float(s["rr"]), 2)
    exp_ret = round(float(s["expected_return_pct"]), 2)

    timing = (ctx or {}).get("timing", {})
    entry_until = _to_berlin(timing.get("entry_until", "")) if timing.get("entry_until") else ""
    est_exit = _to_berlin(timing.get("est_exit", "")) if timing.get("est_exit") else ""
    force_exit = _to_berlin(timing.get("force_exit", "")) if timing.get("force_exit") else ""

    extra = ""
    if entry_until:
        extra += f"\nEnter before: {entry_until}"
    if est_exit:
        extra += f"\nExpected exit: {est_exit}"
    if force_exit:
        extra += f"\nMax hold until: {force_exit}"

    signal_time = _to_berlin(s["timestamp"])

    return (
        f"{direction} for {coin}\n"
        f"Current price: {price} USDT\n"
        f"Target price:  {target} USDT\n"
        f"Stop level:    {stop} USDT\n"
        f"Potential gain: {exp_ret}%  |  R:R {rr}:1\n"
        f"Confidence: {conf_label} ({conf_score})\n"
        f"Signal time: {signal_time}{mood}{extra}"
    )
