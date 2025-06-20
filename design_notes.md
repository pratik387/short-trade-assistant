# 🧠 Design Notes — Short Trade Assistant

This file documents the strategy logic, decision principles, and architecture heuristics that guide both development and analysis.

---

## 🎯 Strategy Philosophy

- **Entry Focus:** Score-based filtering using technical indicators (RSI, ADX, MACD, BB, etc.)
- **Exit Focus:** Modular filter evaluation using a score threshold (soft_exit_threshold)
- **Automation-First:** Design to support automated buying/selling + mock testing

---

## 📐 Architectural Principles

- Use `filters/` for both entry and exit logic as isolated modules
- Route APIs via `routes/` and delegate business logic to `services/`
- Broker access abstracted using `brokers/` folder (Kite, Mock, etc.)
- In-memory + file-based tracking via `tinydb` inside `db/`

---

## 🔄 Entry Strategy

- Evaluates 180-day historical data
- Calculates indicators:
  - `RSI`, `ADX`, `MACD`, `BB`, `Stochastic`, `OBV`, `ATR`, `Candle Patterns`
- Combines into score based on `filters_config.json` weights
- Suggestions shown in dashboard with "Track" and "Score"

---

## 🔁 Exit Strategy

- Uses a separate `evaluate_exit_filters()` with:
  - `ATR Nudge`, `MA Cross`, `RSI Drop`, `ADX`, `MACD`, `ATR Squeeze`, `Fibonacci`, `Time Decay`
- Filters return `(bool allow_exit, reason)`
- Scores are accumulated and compared to `soft_exit_threshold`
- If override filters (stop loss/profit target) trigger, they bypass all

---

## 🧩 Reusability Strategy

- `technical_analysis.py` used for indicator calc (entry)
- `technical_analysis_exit.py` used for indicator + filter gateway (exit)
- Each filter self-contained in a module and loaded via config

---

## 🧪 Backtesting Strategy (Planned)

- Simulate each stock in `portfolio.json` from buy_time
- Re-evaluate exit daily using historical data + exit filters
- Track:
  - `exit triggered`, `PnL`, `holding days`, `triggering filter`
- Summarize performance (accuracy, avg return, max loss)

---

## ✅ Future Plans

- Adaptive learning (reweight filters based on success)
- Regime detection (bull/bear/sideways)
- Unified modal to check entry/exit side-by-side
- Smart notifications via email / WhatsApp
- Full broker sync (real portfolio display)


---

## 📁 Folder Structure (Summary)

```
📁 assets
    📁 indexes
        📄 nifty_100.json
        📄 nifty_200.json
        📄 nifty_50.json
        📄 nifty_500.json
        📄 nse_all.json
    📄 nse_holidays.json
📁 brokers
    📁 data
        📄 indexes.py
    📁 kite
        📄 kite_broker.py
        📄 kite_client.py
    📁 mock
        📄 mock_broker.py
    📄 base_broker.py
📁 config
    📄 env_setup.py
    📄 filters_config.json
    📄 filters_setup.py
📁 db
    📁 tinydb
        📁 tables
            📄 portfolio.json
        📄 client.py
📁 exceptions
    📄 exceptions.py
📁 jobs
    📄 refresh_holidays.py
    📄 refresh_instrument_cache.py
📁 routes
    📄 cache_router.py
    📄 kite_auth_router.py
    📄 notification_router.py
    📄 pnl_router.py
... (see folder_tree.txt for full tree)
```

