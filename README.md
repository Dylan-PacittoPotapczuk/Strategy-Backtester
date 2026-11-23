# Strategy Backtester (Phase B)

Historical equity/ETF backtester with risk guardrails. Phase B adds **momentum** and **mean reversion** (long-only) plus a **Compare** screen that overlays strategies on the same universe, period, and guardrails.

**Stack:** Python 3.11+ / FastAPI engine · React + Vite + TypeScript UI · SQLite run store · free Yahoo Finance EOD data (chart API; same free source as yfinance)

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://127.0.0.1:5173 (Vite proxies `/api` → backend `:8000`)

### Example: single backtest (momentum)

```bash
curl -s -X POST http://127.0.0.1:8000/api/backtests \
  -H 'Content-Type: application/json' \
  -d '{
    "symbols": ["SPY", "QQQ", "IWM"],
    "start_date": "2020-01-01",
    "end_date": "2023-12-31",
    "initial_cash": 100000,
    "currency": "USD",
    "strategy": {
      "type": "momentum",
      "symbols": ["SPY", "QQQ", "IWM"],
      "params": {
        "lookback": 63,
        "top_n": 2,
        "rebalance_days": 21,
        "skip_recent_days": 0,
        "weighting": "equal"
      }
    },
    "guardrails": {
      "max_position_pct": 0.25,
      "max_trade_loss_pct": 0.10,
      "max_portfolio_drawdown_pct": 0.20,
      "sizing_mode": "equal_weight",
      "flatten_on_breach": false
    },
    "costs": {
      "slippage_bps": 5,
      "commission_per_trade": 0
    }
  }' | python3 -m json.tool
```

### Example: compare strategies

```bash
curl -s -X POST http://127.0.0.1:8000/api/compare \
  -H 'Content-Type: application/json' \
  -d '{
    "symbols": ["SPY", "QQQ", "IWM"],
    "start_date": "2020-01-01",
    "end_date": "2023-12-31",
    "initial_cash": 100000,
    "strategies": [
      {"type": "buy_and_hold", "symbols": ["SPY", "QQQ", "IWM"], "params": {}},
      {"type": "momentum", "symbols": ["SPY", "QQQ", "IWM"], "params": {"lookback": 63, "top_n": 2, "rebalance_days": 21}},
      {"type": "mean_reversion", "symbols": ["SPY", "QQQ", "IWM"], "params": {"window": 20, "entry_z": 1.5, "exit_z": 0.25, "max_positions": 2}}
    ],
    "guardrails": {
      "max_position_pct": 0.25,
      "max_trade_loss_pct": 0.10,
      "max_portfolio_drawdown_pct": 0.20,
      "sizing_mode": "equal_weight",
      "flatten_on_breach": false
    },
    "costs": {"slippage_bps": 5, "commission_per_trade": 0}
  }' | python3 -m json.tool
```

### UI flow

1. **Configure** → pick buy & hold / momentum / mean reversion, set params (each field has a “?” definition), symbols, dates, cash, guardrails, costs → **Run backtest**.
2. **Results** → equity curve, drawdown, metrics, trade blotter.
3. **Compare** → same shared setup; select one or more strategies → **Run comparison** → overlay equity curves + metrics table (return, Sharpe, max DD, stop / DD-halt counts). Open any row’s “View run” for full results.

## Strategies (Phase B)

| Strategy | Rule (summary) | Key params |
|----------|----------------|------------|
| Buy & hold | Allocate once; hold unless risk rules sell | Optional weights |
| Momentum | Rank by trailing return; long top-N; rebalance on schedule | `lookback`, `top_n`, `rebalance_days`, `skip_recent_days`, `weighting` |
| Mean reversion | Long when z-score ≤ −entry; exit when z ≥ −exit (or time stop) | `window`, `entry_z`, `exit_z`, `max_positions`, `max_hold_days?` |

Signals use closes through the signal day only; fills are at the **next open** (no look-ahead).

## Execution assumptions (locked)

| Rule | Value |
|------|--------|
| Markets | Equities / ETFs, long-only, USD |
| Fill | Next open after signal |
| Costs | ~5 bps slippage, $0 commission (defaults) |
| Data | Free Yahoo Finance EOD (adjusted) via chart API; SQLite OHLCV cache |
| DD breach | Halt new risk; do **not** auto-flatten |

## Tests

```bash
cd backend
python3 -m pytest -q
```

Covers fill lag, position sizing, stop-loss, drawdown halt, momentum ranking / next-open fill, and mean-reversion entry/exit / no look-ahead.

## Repo layout

```
backend/
  app/           # FastAPI + engine + data adapters
  tests/         # Unit tests (fixture data, no network)
frontend/        # React + Vite + TypeScript
```

## Phase status

| Done | Deferred |
|------|----------|
| Buy-and-hold, momentum, mean reversion | Monte Carlo (Phase C) |
| Configure + Results + Compare UI | Postgres / auth |
| Backtest + compare API + SQLite | Paid data vendors |
| Risk guardrails (size / stop / DD halt) | Shorts / leverage |

## License

MVP / personal use — no paid APIs required to run.
