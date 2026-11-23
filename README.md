# Strategy Backtester

Historical equity/ETF backtester with risk guardrails, **walk-forward / out-of-sample splits**, **benchmark overlays** (default SPY), **saved runs + config presets**, Monte Carlo forward projections, and a Compare screen.

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

### Example: single backtest with walk-forward + benchmark

```bash
curl -s -X POST http://127.0.0.1:8000/api/backtests \
  -H 'Content-Type: application/json' \
  -d '{
    "symbols": ["SPY", "QQQ", "IWM"],
    "start_date": "2020-01-01",
    "end_date": "2023-12-31",
    "initial_cash": 100000,
    "currency": "USD",
    "name": "Momentum 70/30 OOS",
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
    "costs": { "slippage_bps": 5, "commission_per_trade": 0 },
    "walk_forward": { "enabled": true, "mode": "percent", "train_pct": 0.7 },
    "benchmark": { "enabled": true, "symbol": "SPY" }
  }' | python3 -m json.tool
```

Walk-forward modes: `"percent"` (share of trading days) or `"date"` with `"split_date": "2022-01-01"`. Same strategy rules run on the full window; metrics are reported separately for in-sample vs out-of-sample. This is **not** automatic parameter search.

### Example: presets & saved runs

```bash
# List recent runs (name + timestamp + headline fields)
curl -s http://127.0.0.1:8000/api/runs | python3 -m json.tool

# Save a Configure-form preset (no auth; local SQLite)
curl -s -X POST http://127.0.0.1:8000/api/presets \
  -H 'Content-Type: application/json' \
  -d '{"name":"My momentum setup","config":{"strategyType":"momentum"}}' | python3 -m json.tool

curl -s http://127.0.0.1:8000/api/presets | python3 -m json.tool
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
    "costs": {"slippage_bps": 5, "commission_per_trade": 0},
    "walk_forward": {"enabled": true, "mode": "percent", "train_pct": 0.7},
    "benchmark": {"enabled": true, "symbol": "SPY"}
  }' | python3 -m json.tool
```

### UI flow

1. **Configure** → strategy + params (“?” definitions), symbols, dates, cash, guardrails, costs, optional walk-forward split, benchmark symbol, optional run name / presets → **Run backtest**.
2. **Results** → equity vs benchmark, drawdown, full + IS/OOS metrics when walk-forward is on, excess-return strip, trade blotter, Monte Carlo. Warns when tuning without OOS.
3. **Compare** → shared setup including walk-forward + benchmark; overlay curves + metrics table (IS/OOS + excess columns when enabled).
4. **Saved runs** → reopen recent SQLite-backed runs; rename; load Configure presets from the Configure screen.

## Strategies

| Strategy | Rule (summary) | Key params |
|----------|----------------|------------|
| Buy & hold | Allocate once; hold unless risk rules sell | Optional weights |
| Momentum | Rank by trailing return; long top-N; rebalance on schedule | `lookback`, `top_n`, `rebalance_days`, `skip_recent_days`, `weighting` |
| Mean reversion | Long when z-score ≤ −entry; exit when z ≥ −exit (or time stop) | `window`, `entry_z`, `exit_z`, `max_positions`, `max_hold_days?` |

Signals use closes through the signal day only; fills are at the **next open** (no look-ahead).

## Walk-forward & benchmarks

| Feature | Detail |
|---------|--------|
| Walk-forward | Percent or date split; in-sample vs out-of-sample metrics on the continuous equity curve; UI warns when disabled |
| Benchmark | Buy-and-hold of configurable symbol (default **SPY**); equity overlay; excess return / CAGR / Sharpe vs strategy |
| Alignment | Strategy calendar intersects benchmark trading days so series share dates |
| Compare | Same walk-forward + benchmark apply to every strategy in the overlay |

## Monte Carlo

| Item | Detail |
|------|--------|
| Input | Backtest `daily_returns` (after costs & guardrails) |
| Sampler | i.i.d. bootstrap, or optional **block bootstrap** (`block_size` ~5–21) |
| Defaults | 500 paths · 252-day horizon · optional seed · start equity = backtest terminal |
| Assumption | Path-dependent guardrails are **not** re-applied on synthetic paths — disclosed in the Results UI |

## Saved runs & presets

| API | Purpose |
|-----|---------|
| `GET /api/runs` | Recent run summaries (name, time, strategy, return) |
| `PATCH /api/backtests/{id}/name` | Rename a run |
| `GET/POST /api/presets`, `PATCH/DELETE /api/presets/{id}` | Config presets (local SQLite, no auth) |

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

Covers fill lag, sizing, stops, drawdown halt, momentum / mean-reversion, Monte Carlo, **walk-forward split correctness**, and **benchmark series alignment**.

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
| Configure + Results + Compare + Saved runs | Paid data vendors |
| Walk-forward IS/OOS + SPY (override) benchmark | Shorts / leverage |
| Config presets + named runs (SQLite) | Re-apply stops on MC paths |
| Risk guardrails + Monte Carlo bands | Background job worker (if paths get heavy) |
| Parameter auto-search / optimizer UI | — |

## License

MVP / personal use — no paid APIs required to run.
