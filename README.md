# Strategy Backtester (Phase C)

Historical equity/ETF backtester with risk guardrails. Phase C adds **Monte Carlo forward projections** from a completed backtest’s daily return series (bootstrap or block-bootstrap), with percentile equity bands and a terminal return summary.

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

### Example: Monte Carlo from a completed backtest

```bash
# Replace RUN_ID with the id from a done backtest response
curl -s -X POST "http://127.0.0.1:8000/api/backtests/RUN_ID/monte-carlo" \
  -H 'Content-Type: application/json' \
  -d '{
    "n_paths": 500,
    "horizon_days": 252,
    "seed": 42,
    "block_bootstrap": false
  }' | python3 -m json.tool
```

Optional: `"block_bootstrap": true, "block_size": 10` to resample short contiguous blocks (mild autocorrelation). Defaults cap at **500 paths** (API max 2,000) for snappy UX.

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
2. **Results** → equity curve, drawdown, metrics, trade blotter, then **Run forward projection** for Monte Carlo percentile bands + terminal return summary.
3. **Compare** → same shared setup; select strategies → **Run comparison** → overlay equity curves + metrics table. Open any row’s **View run** for full results and MC.

## Strategies (Phase B)

| Strategy | Rule (summary) | Key params |
|----------|----------------|------------|
| Buy & hold | Allocate once; hold unless risk rules sell | Optional weights |
| Momentum | Rank by trailing return; long top-N; rebalance on schedule | `lookback`, `top_n`, `rebalance_days`, `skip_recent_days`, `weighting` |
| Mean reversion | Long when z-score ≤ −entry; exit when z ≥ −exit (or time stop) | `window`, `entry_z`, `exit_z`, `max_positions`, `max_hold_days?` |

Signals use closes through the signal day only; fills are at the **next open** (no look-ahead).

## Monte Carlo (Phase C)

| Item | Detail |
|------|--------|
| Input | Backtest `daily_returns` (after costs & guardrails) |
| Sampler | i.i.d. bootstrap, or optional **block bootstrap** (`block_size` ~5–21) |
| Defaults | 500 paths · 252-day horizon · optional seed · start equity = backtest terminal |
| Outputs | Percentile bands (p5 / p25 / p50 / p75 / p95) by day; terminal return mean / std / p5 / p50 / p95; P(end below start) |
| API | `POST /api/backtests/{id}/monte-carlo`, `GET /api/monte-carlo/{mc_id}`, `GET /api/backtests/{id}/monte-carlo` |
| Assumption | Path-dependent guardrails are **not** re-applied on synthetic paths — disclosed in the Results UI |

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

Covers fill lag, position sizing, stop-loss, drawdown halt, momentum / mean-reversion, and Monte Carlo seed determinism + band shape.

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
| Buy-and-hold, momentum, mean reversion | Postgres / auth |
| Configure + Results + Compare UI | Paid data vendors |
| Backtest + compare API + SQLite | Shorts / leverage |
| Risk guardrails (size / stop / DD halt) | Re-apply stops on MC paths |
| Monte Carlo bootstrap / block-bootstrap + bands | Background job worker (if paths get heavy) |

## License

MVP / personal use — no paid APIs required to run.
