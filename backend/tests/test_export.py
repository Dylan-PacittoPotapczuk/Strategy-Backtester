"""CSV export contents + PDF generation smoke tests."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.export.csv_export import build_backtest_csv_zip, build_compare_csv_zip
from app.export.pdf_export import build_backtest_pdf, build_compare_pdf
from app.main import app
from app.models.schemas import (
    BacktestRequest,
    BacktestResponse,
    BacktestStatus,
    CostConfig,
    EquityPoint,
    GuardrailConfig,
    Metrics,
    MonteCarloRequest,
    MonteCarloResponse,
    MonteCarloResult,
    PercentileBand,
    StrategyConfig,
    TerminalReturnDist,
    Trade,
    TradeReason,
    TradeSide,
)


def _strategy_params(strategy: str) -> dict:
    if strategy == "momentum":
        return {
            "lookback": 63,
            "top_n": 2,
            "rebalance_days": 21,
            "skip_recent_days": 0,
            "weighting": "equal",
        }
    if strategy == "mean_reversion":
        return {
            "window": 20,
            "entry_z": 1.5,
            "exit_z": 0.25,
            "max_positions": 2,
        }
    return {}


def _sample_run(strategy: str = "buy_and_hold") -> BacktestResponse:
    run_id = uuid4()
    req = BacktestRequest(
        symbols=["SPY", "QQQ"],
        start_date=date(2024, 1, 2),
        end_date=date(2024, 1, 10),
        initial_cash=100_000.0,
        strategy=StrategyConfig(
            type=strategy,  # type: ignore[arg-type]
            symbols=["SPY", "QQQ"],
            params=_strategy_params(strategy),
        ),
        guardrails=GuardrailConfig(
            max_position_pct=0.25,
            max_trade_loss_pct=0.10,
            max_portfolio_drawdown_pct=0.20,
        ),
        costs=CostConfig(slippage_bps=5.0, commission_per_trade=0.0),
        name="Export fixture",
    )
    metrics = Metrics(
        total_return=0.12,
        cagr=0.08,
        volatility=0.15,
        sharpe=1.1,
        max_drawdown=0.05,
        win_rate=0.55,
        num_trades=4,
        num_stop_losses=1,
        num_dd_halts=0,
        final_equity=112_000.0,
        initial_cash=100_000.0,
        trading_days=7,
    )
    equity = [
        EquityPoint(date=date(2024, 1, 2), equity=100_000.0, cash=20_000.0, drawdown_pct=0.0),
        EquityPoint(date=date(2024, 1, 3), equity=101_000.0, cash=20_000.0, drawdown_pct=0.0),
        EquityPoint(date=date(2024, 1, 4), equity=99_500.0, cash=20_000.0, drawdown_pct=0.01485),
        EquityPoint(date=date(2024, 1, 5), equity=112_000.0, cash=15_000.0, drawdown_pct=0.0),
    ]
    trades = [
        Trade(
            symbol="SPY",
            side=TradeSide.BUY,
            qty=10,
            price=400.0,
            ts=date(2024, 1, 3),
            reason=TradeReason.SIGNAL,
        ),
        Trade(
            symbol="SPY",
            side=TradeSide.SELL,
            qty=10,
            price=390.0,
            ts=date(2024, 1, 4),
            reason=TradeReason.STOP_LOSS,
            pnl=-100.0,
            pnl_pct=-0.025,
            note="pnl_pct=-0.025 <= -0.10",
        ),
    ]
    return BacktestResponse(
        id=run_id,
        created_at=datetime.now(timezone.utc),
        status=BacktestStatus.DONE,
        request=req,
        name="Export fixture",
        equity_curve=equity,
        trades=trades,
        metrics=metrics,
        daily_returns=[0.01, -0.005, 0.02],
        dd_halted=False,
    )


def _sample_mc(run_id) -> MonteCarloResponse:
    return MonteCarloResponse(
        id=uuid4(),
        created_at=datetime.now(timezone.utc),
        backtest_run_id=run_id,
        request=MonteCarloRequest(n_paths=100, horizon_days=10, seed=1),
        result=MonteCarloResult(
            percentile_bands=[
                PercentileBand(day=1, p5=99_000, p25=100_000, p50=101_000, p75=102_000, p95=103_000),
                PercentileBand(day=2, p5=98_000, p25=100_500, p50=102_000, p75=103_500, p95=105_000),
            ],
            terminal_return_dist=TerminalReturnDist(
                mean=0.05,
                std=0.1,
                p5=-0.1,
                p50=0.04,
                p95=0.2,
                prob_below_start=0.3,
            ),
            start_equity=112_000.0,
            n_paths=100,
            horizon_days=10,
            block_bootstrap=False,
            seed=1,
            assumptions="Test assumptions text",
        ),
    )


def _read_zip_csv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    with zf.open(name) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8")
        return list(csv.DictReader(text))


def test_backtest_csv_zip_contains_metrics_equity_trades() -> None:
    run = _sample_run()
    raw = build_backtest_csv_zip(run, monte_carlo=None)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert names == {"metrics.csv", "equity.csv", "trades.csv"}

        metrics = {row["key"]: row["value"] for row in _read_zip_csv(zf, "metrics.csv")}
        assert metrics["run_id"] == str(run.id)
        assert metrics["strategy"] == "buy_and_hold"
        assert metrics["symbols"] == "SPY,QQQ"
        assert float(metrics["total_return"]) == pytest.approx(0.12)
        assert float(metrics["sharpe"]) == pytest.approx(1.1)
        assert metrics["num_stop_losses"] == "1"
        assert float(metrics["slippage_bps"]) == pytest.approx(5.0)

        equity = _read_zip_csv(zf, "equity.csv")
        assert len(equity) == 4
        assert equity[0]["date"] == "2024-01-02"
        assert float(equity[-1]["equity"]) == pytest.approx(112_000.0)

        trades = _read_zip_csv(zf, "trades.csv")
        assert len(trades) == 2
        assert trades[0]["symbol"] == "SPY"
        assert trades[0]["side"] == "buy"
        assert trades[1]["reason"] == "stop_loss"
        assert float(trades[1]["pnl"]) == pytest.approx(-100.0)


def test_backtest_csv_includes_mc_when_present() -> None:
    run = _sample_run()
    mc = _sample_mc(run.id)
    raw = build_backtest_csv_zip(run, monte_carlo=mc)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        assert "mc_summary.csv" in zf.namelist()
        assert "mc_bands.csv" in zf.namelist()
        summary = {row["key"]: row["value"] for row in _read_zip_csv(zf, "mc_summary.csv")}
        assert summary["n_paths"] == "100"
        assert float(summary["terminal_p50"]) == pytest.approx(0.04)
        assert "Test assumptions" in summary["assumptions"]
        bands = _read_zip_csv(zf, "mc_bands.csv")
        assert len(bands) == 2
        assert bands[0]["day"] == "1"
        assert float(bands[1]["p95"]) == pytest.approx(105_000.0)


def test_compare_csv_zip() -> None:
    runs = [_sample_run("buy_and_hold"), _sample_run("momentum")]
    raw = build_compare_csv_zip(runs)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "compare_metrics.csv" in names
        assert "equity_momentum.csv" in names
        assert "trades_buy_and_hold.csv" in names
        rows = _read_zip_csv(zf, "compare_metrics.csv")
        assert {r["strategy"] for r in rows} == {"buy_and_hold", "momentum"}
        assert all(float(r["total_return"]) == pytest.approx(0.12) for r in rows)


def test_pdf_smoke_backtest_and_compare() -> None:
    run = _sample_run()
    mc = _sample_mc(run.id)
    pdf = build_backtest_pdf(run, monte_carlo=mc)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 500

    compare_pdf = build_compare_pdf([run, _sample_run("mean_reversion")])
    assert compare_pdf[:4] == b"%PDF"
    assert len(compare_pdf) > 400


def test_export_http_endpoints(tmp_path, monkeypatch) -> None:
    """Smoke the FastAPI export routes with an in-memory stored run."""
    from app.api import routes as routes_mod
    from app.db import RunStore

    db = tmp_path / "export-test.sqlite"
    store = RunStore(db_path=db)
    monkeypatch.setattr(routes_mod, "store", store)

    run = _sample_run()
    # Persist via store internals: create then update
    created = store.create(run.request)
    created.status = BacktestStatus.DONE
    created.equity_curve = run.equity_curve
    created.trades = run.trades
    created.metrics = run.metrics
    created.daily_returns = run.daily_returns
    created.name = run.name
    store.update(created)

    mc_result = _sample_mc(created.id).result
    store.create_monte_carlo(
        created.id,
        MonteCarloRequest(n_paths=100, horizon_days=10, seed=1),
        mc_result,
    )

    client = TestClient(app)
    # Re-bind store on the live router module used by app
    monkeypatch.setattr(routes_mod, "store", store)

    csv_res = client.get(f"/api/backtests/{created.id}/export.csv")
    assert csv_res.status_code == 200
    assert csv_res.headers["content-type"].startswith("application/zip")
    with zipfile.ZipFile(io.BytesIO(csv_res.content)) as zf:
        assert "metrics.csv" in zf.namelist()
        assert "mc_summary.csv" in zf.namelist()
        metrics = {row["key"]: row["value"] for row in _read_zip_csv(zf, "metrics.csv")}
        assert float(metrics["total_return"]) == pytest.approx(0.12)

    pdf_res = client.get(f"/api/backtests/{created.id}/export.pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"].startswith("application/pdf")
    assert pdf_res.content[:4] == b"%PDF"

    body = {"runs": [created.model_dump(mode="json")]}
    # Reload full run for export body
    full = store.get(created.id)
    assert full is not None
    body = {"runs": [full.model_dump(mode="json")]}

    c_csv = client.post("/api/compare/export.csv", json=body)
    assert c_csv.status_code == 200
    assert c_csv.headers["content-type"].startswith("application/zip")

    c_pdf = client.post("/api/compare/export.pdf", json=body)
    assert c_pdf.status_code == 200
    assert c_pdf.content[:4] == b"%PDF"
