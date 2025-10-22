# === API / Source ===
COINGECKO_API_KEY = ""   # not used now
VS_CURRENCY = "eur"

# Track these coins (mapped to Binance USDT pairs below)
COIN_IDS = [
    "bitcoin", "ethereum", "binancecoin", "ripple",
    "solana", "cardano", "dogecoin", "tron",
    "chainlink", "litecoin"
]

# Binance source (free)
BINANCE_INTERVAL = "1h"
BINANCE_LIMIT = 1000      # max 1000 → enough for EMA200 on 5m

# Map CoinGecko IDs -> Binance symbols
SYMBOL_MAP = {
    "bitcoin": "BTCUSDT",
    "ethereum": "ETHUSDT",
    "binancecoin": "BNBUSDT",
    "ripple": "XRPUSDT",
    "solana": "SOLUSDT",
    "cardano": "ADAUSDT",
    "dogecoin": "DOGEUSDT",
    "tron": "TRXUSDT",
    "chainlink": "LINKUSDT",
    "litecoin": "LTCUSDT",
}

# === Strategy ===
MIN_EXPECTED_RETURN_PCT = 5.0
MIN_RR = 1.5
DATA_FRESHNESS_SEC = 1800
EMA_LEN = 200
RSI_LEN = 14
ATR_LEN = 14

# === Telegram ===
TELEGRAM_BOT_TOKEN = "8218118041:AAFkzrSAEySMA0ByJRdLFz9sVI6GNQYB_l4"
TELEGRAM_CHAT_ID = "8361416364"

# === Files ===
DATA_DIR = "data"
LOG_FILE = "data/signals.csv"
