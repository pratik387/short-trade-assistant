# 📊 Trade Assistant

An intelligent, broker-agnostic assistant for short-term and intraday stock trading. Built with modular architecture, it supports both live trades (e.g., Kite by Zerodha) and mock simulations for backtesting strategies.

---

## 🏠 Project Structure

```
backend/
├── assets/                    # Static data files (e.g. symbol lists)
├── brokers/                  # Broker-specific clients and data providers
│   ├── base_broker.py        # Broker interface
│   └── kite/                 # Zerodha Kite integration
│       ├── kite_broker.py
│       ├── kite_client.py
│       ├── kite_data_provider.py
│       └── kite_exit_data_provider.py
├── config/                   # Config files and loaders
│   ├── filters_config.json   # Exit and entry filter weights
│   └── settings.py
├── db/
│   └── tinydb/               # Lightweight NoSQL storage layer
│       └── client.py
├── jobs/                     # Scheduled or CLI-triggered jobs
│   ├── mock_trade_analyzer.py
│   ├── refresh_holidays.py
│   └── refresh_instrument_cache.py
├── routes/                   # FastAPI API endpoints
│   ├── kite_auth_router.py
│   ├── portfolio_router.py
│   ├── suggestion_router.py
│   └── ...
├── schedulers/              # APScheduler background job manager
│   └── scheduler.py
├── services/                # Core trading logic and orchestrators
│   ├── entry_service.py
│   ├── exit_service.py
│   ├── exit_job_runner.py
│   ├── trade_executor.py
│   ├── technical_analysis.py
│   ├── suggestion_logic.py
│   ├── filters/             # Modular filter logic
│   │   ├── rsi_filter.py
│   │   ├── macd_filter.py
│   │   └── ...
│   └── notification/        # Alerting logic (email, Slack, etc.)
│       └── email_alert.py
```

---

## ⚙️ Key Components

- **Entry & Exit Services**: Decides when to buy/sell based on config-weighted indicators.
- **Trade Executor**: Handles both real and mock trades, logs outcomes.
- **TinyDB**: Used for storing portfolio and mock trades without heavy setup.
- **Scheduler**: Automates exit checks, data refreshes, and holiday downloads.
- **FastAPI Routers**: Exposes endpoints to UI for suggestions, portfolio, and manual triggers.

---

## 🚀 To Run

```bash
# Development mode
uvicorn main:app --reload

# Production with Gunicorn
gunicorn -k uvicorn.workers.UvicornWorker main:app
```

Make sure to define environment variables in a `.env` file:

```
KITE_API_KEY=your_key
KITE_API_SECRET=your_secret
GMAIL_USER=your_email@gmail.com
GMAIL_PASS=your_password
ALERT_TO=recipient@example.com
```

---

## 📂 FastAPI API Docs

FastAPI provides interactive documentation out of the box:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

Optional health check:

```python
@router.get("/api/health")
def health():
    return {"status": "ok"}
```

---

## 📊 Features

- Broker-Agnostic Interface (via `BaseBroker`)
- Hybrid Exit Strategy: Targets + Trailing SL + RSI + MA
- Live and Mock Trade Support
- Modular Filters (RSI, MACD, BB, OBV, Stochastic, etc.)
- PnL Analysis and Simulation
- Auto-refresh NSE Index Constituents & Holidays
- Email Alerts for Exit Triggers

---

## 🗓️ Suggested Crons

| Task                 | Frequency | Description                          |
|----------------------|-----------|--------------------------------------|
| Refresh index cache  | Daily     | Updates symbol-token mappings        |
| Exit checks          | 5 min     | Checks if any stock needs exiting    |
| NSE holiday refresh  | Yearly    | Updates NSE trading holiday calendar |

---

## 🧰 Testing Trades (Mock Mode)

```python
from backend.services.trade_executor import TradeExecutor

executor = TradeExecutor(mode="mock")
executor.execute_trade("INFY.NS", 10, "BUY")
```

---

## 📬 Exit Alerts

Email is sent on exit trigger using `email_alert.py`. You can extend this to Slack/Telegram.

---

## 🔮 TODO

- Web UI for visualizing mock P&L and charts
- Broker support for Upstox, AngelOne
- Candlestick pattern and volume exhaustion filters
- Adaptive learning filters using past trades
