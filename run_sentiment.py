from datetime import datetime, timezone
from src.agents.sentiment import SentimentAgent

agent = SentimentAgent()
universe = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
res = agent.run(universe, datetime.now(tz=timezone.utc))
for r in res:
    print(r)
