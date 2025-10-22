# Copy to config.py and fill in. Never commit config.py.
COINGECKO_API_KEY = ""  # optional
VS_CURRENCY = "eur"
COIN_IDS = [
    "bitcoin","ethereum","tether","ripple","binancecoin","solana","usd-coin",
    "dogecoin","tron","cardano","chainlink","avalanche-2","stellar","sui",
    "bitcoin-cash","polkadot","uniswap","near","polygon-pos","litecoin",
    "internet-computer","aave","vechain","cosmos","filecoin","maker",
    "optimism","arbitrum","aptos","hedera","mantle","monero","quant-network",
    "algorand","immutable-x","the-graph","bittensor","fantom","thorchain",
    "lido-dao","sei-network","bonk","beam-2","jupiter-exchange-solana",
    "coredaoorg","gala","onda","injective","celestia","conflux-token"
]
MIN_EXPECTED_RETURN_PCT = 5.0
MIN_RR = 1.2
DATA_FRESHNESS_SEC = 1800 # 30 minutes
EMA_LEN = 200
RSI_LEN = 14
ATR_LEN = 14
TELEGRAM_BOT_TOKEN = "8218118041:AAFkzrSAEySMA0ByJRdLFz9sVI6GNQYB_l4"
TELEGRAM_CHAT_ID = "8361416364"
DATA_DIR = "data"
LOG_FILE = "data/signals.csv"
