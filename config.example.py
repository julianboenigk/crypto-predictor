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
MIN_EXPECTED_RETURN_PCT = 15.0
MIN_RR = 1.5
DATA_FRESHNESS_SEC = 120
EMA_LEN = 200
RSI_LEN = 14
ATR_LEN = 14
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""
DATA_DIR = "data"
LOG_FILE = "data/signals.csv"
