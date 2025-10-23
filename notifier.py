import requests
import config

def send_telegram(text: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode":"HTML"}, timeout=20)
    return r.ok

def fmt_signal(s: dict, ctx: dict | None = None) -> str:
    fng = ctx.get("fng") if ctx else {}
    fng_str = ""
    if fng and fng.get("value") is not None:
        fng_str = f"\nF&G: {fng['value']} ({fng['classification']})"
    return (
        f"<b>{s['coin_id']}</b> {s['signal']}\n"
        f"Price: {s['price']} {config.VS_CURRENCY.upper()}\n"
        f"EMA200: {s['ema200']} | RSI14: {s['rsi14']} | ATR14: {s['atr14']}\n"
        f"Stop: {s['stop']} | Target: {s['target']} | R:R {s['rr']}\n"
        f"Exp. Return: {s['expected_return_pct']}%\n"
        f"Time: {s['timestamp']}{fng_str}"
    )
