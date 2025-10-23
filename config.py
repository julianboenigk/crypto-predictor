# === API / Source ===
VS_CURRENCY = "eur"          # cosmetic in messages
# Binance klines (free)
BINANCE_INTERVAL = "1h"      # use 1h for larger swings
BINANCE_LIMIT = 1000

# === Universe ===
# Static fallback list (used if dynamic fetch fails)
COIN_IDS = [
    "bitcoin","ethereum","binancecoin","ripple","solana",
    "cardano","dogecoin","tron","chainlink","litecoin"
]
# Map CoinGecko IDs -> Binance symbols
SYMBOL_MAP = {
    "bitcoin":"BTCUSDT","ethereum":"ETHUSDT","binancecoin":"BNBUSDT","ripple":"XRPUSDT",
    "solana":"SOLUSDT","cardano":"ADAUSDT","dogecoin":"DOGEUSDT","tron":"TRXUSDT",
    "chainlink":"LINKUSDT","litecoin":"LTCUSDT",
}
USE_DYNAMIC_SYMBOLS = True    # pull top-volume pairs automatically
DYNAMIC_TOP_N = 30            # analyze top 30 USDT pairs

# === Strategy ===
MIN_EXPECTED_RETURN_PCT = 7.0   # realistic on 1h
MIN_RR = 1.5
DATA_FRESHNESS_SEC = 1800
EMA_LEN = 200
RSI_LEN = 14
ATR_LEN = 14

# Timing guidance (adds “enter before / expected exit / max hold until”)
ENTRY_VALID_BARS = 2             # signal fresh for next N bars
MAX_HOLD_BARS   = 48             # force exit after M bars

# === Telegram ===
TELEGRAM_BOT_TOKEN = "8218118041:AAFkzrSAEySMA0ByJRdLFz9sVI6GNQYB_l4"
TELEGRAM_CHAT_ID = "8361416364"

# === Files ===
DATA_DIR = "data"
LOG_FILE = "data/signals.csv"
