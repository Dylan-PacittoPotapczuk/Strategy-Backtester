# Strategy Backtester (Phase A)

Historical equity/ETF backtester with risk guardrails. Phase A ships **buy-and-hold** only, with position sizing, per-trade loss limits, and portfolio drawdown halt (no auto-flatten).

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

### Example: curl

```bash
curl -s -X POST http://127.0.0.1:8000/api/backtests \
  -H 'Content-Type: application/json' \
  -d '{
    "symbols": ["SPY", "QQQ"],
    "start_date": "2020-01-01",
    "end_date": "2023-12-31",
    "initial_cash": 100000,
    "currency": "USD",
    "strategy": {
      "type": "buy_and_hold",
      "symbols": ["SPY", "QQQ"],
      "params": {}
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

### UI flow

1. Open **Configure** → set symbols, dates, cash, guardrail %, costs.
2. Click **Run backtest**.
3. **Results** shows equity curve, drawdown, metrics strip, and trade blotter (with reason codes).

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

Covers fill lag, position sizing, stop-loss, and drawdown halt.

## Repo layout

```
backend/
  app/           # FastAPI + engine + data adapters
  tests/         # Unit tests (fixture data, no network)
frontend/        # React + Vite + TypeScript
```

## Phase A vs later

| Done now | Deferred |
|----------|----------|
| Buy-and-hold + risk engine | Momentum, mean reversion |
| Configure + Results UI | Compare screen |
| Backtest API + SQLite | Monte Carlo polish |
| yfinance + fixture adapter | Paid data vendors |

## License

MVP / personal use — no paid APIs required to run.
