# 🧠 Crypto Predictor — Project Plan

_Last updated: 2025-10-30_

This document tracks open tasks, implementation priorities, and current system status for the **Crypto Predictor** project.

---

## ✅ Current System Status

| Component | Status | Description |
|------------|---------|-------------|
| **Main Engine** | ✅ Running | Executes every 15 min via cron. Technical, sentiment, research, and consensus scoring all operational. |
| **News Fetcher** | ⚠️ Temporarily Disabled | Working correctly, but provider (cryptonews-api.com) has blacklisted the current IP. Awaiting unblock. |
| **Sentiment Fetcher** | ⚠️ Temporarily Disabled | API logic implemented (using `/stat` endpoint) but same IP block as news API. |
| **Database (SQLite)** | ✅ OK | Stores trading signals and logs. |
| **Telegram Notifier** | ✅ OK | Configured and tested. |
| **Cron Jobs** | ✅ OK | 15 min (main), hourly (news), hourly (sentiment). |

---

## 🧩 Open Tasks

### 1️⃣ Provider Integration & Stability

- [ ] **Resolve Cryptonews IP Blacklist**  
  Contact provider support (`support@cryptonews-api.com`) with your IP address and request a whitelist/unblock.

- [ ] **Add Automatic Backoff Mechanism**  
  Detect repeated HTTP 403 / timeout errors and skip external API calls for 12–24 h before retrying.

- [ ] **Implement `.env` Safety Guards**  
  Add flags to pause specific refreshers without editing cron:
  ```bash
  NEWS_REFRESH_ENABLED=0
  SENTIMENT_REFRESH_ENABLED=0

