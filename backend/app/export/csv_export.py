"""Build ZIP archives of CSV files for backtest / compare risk reports."""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Optional

from app.models.schemas import BacktestResponse, MonteCarloResponse


def _metrics_rows(run: BacktestResponse) -> list[list[str]]:
    m = run.metrics
    req = run.request
    rows: list[list[str]] = [
        ["key", "value"],
        ["run_id", str(run.id)],
        ["name", run.name or ""],
        ["status", run.status.value if hasattr(run.status, "value") else str(run.status)],
        ["strategy", req.strategy.type],
        ["symbols", ",".join(req.symbols)],
        ["start_date", str(req.start_date)],
        ["end_date", str(req.end_date)],
        ["initial_cash", f"{req.initial_cash:.6f}"],
        ["currency", req.currency],
        ["slippage_bps", f"{req.costs.slippage_bps:.6f}"],
        ["commission_per_trade", f"{req.costs.commission_per_trade:.6f}"],
        ["max_position_pct", f"{req.guardrails.max_position_pct:.6f}"],
        ["max_trade_loss_pct", f"{req.guardrails.max_trade_loss_pct:.6f}"],
        ["max_portfolio_drawdown_pct", f"{req.guardrails.max_portfolio_drawdown_pct:.6f}"],
        ["sizing_mode", req.guardrails.sizing_mode],
        ["flatten_on_breach", str(req.guardrails.flatten_on_breach)],
        ["dd_halted", str(run.dd_halted)],
        ["dd_halt_date", str(run.dd_halt_date) if run.dd_halt_date else ""],
    ]
    if m is not None:
        rows.extend(
            [
                ["total_return", f"{m.total_return:.8f}"],
                ["cagr", f"{m.cagr:.8f}"],
                ["volatility", f"{m.volatility:.8f}"],
                ["sharpe", f"{m.sharpe:.8f}"],
                ["max_drawdown", f"{m.max_drawdown:.8f}"],
                ["win_rate", "" if m.win_rate is None else f"{m.win_rate:.8f}"],
                ["num_trades", str(m.num_trades)],
                ["num_stop_losses", str(m.num_stop_losses)],
                ["num_dd_halts", str(m.num_dd_halts)],
                ["final_equity", f"{m.final_equity:.6f}"],
                ["trading_days", str(m.trading_days)],
            ]
        )
    if run.benchmark and run.benchmark.enabled:
        rows.extend(
            [
                ["benchmark_symbol", run.benchmark.symbol],
                [
                    "excess_return",
                    ""
                    if run.benchmark.excess_return is None
                    else f"{run.benchmark.excess_return:.8f}",
                ],
                [
                    "excess_cagr",
                    ""
                    if run.benchmark.excess_cagr is None
                    else f"{run.benchmark.excess_cagr:.8f}",
                ],
                [
                    "excess_sharpe",
                    ""
                    if run.benchmark.excess_sharpe is None
                    else f"{run.benchmark.excess_sharpe:.8f}",
                ],
            ]
        )
    if run.walk_forward and run.walk_forward.enabled:
        wf = run.walk_forward
        rows.extend(
            [
                ["walk_forward_mode", wf.mode or ""],
                ["walk_forward_split_date", str(wf.split_date) if wf.split_date else ""],
                ["train_trading_days", str(wf.train_trading_days)],
                ["test_trading_days", str(wf.test_trading_days)],
            ]
        )
        if wf.metrics_in_sample:
            rows.append(
                ["in_sample_total_return", f"{wf.metrics_in_sample.total_return:.8f}"]
            )
            rows.append(["in_sample_sharpe", f"{wf.metrics_in_sample.sharpe:.8f}"])
        if wf.metrics_out_of_sample:
            rows.append(
                [
                    "out_of_sample_total_return",
                    f"{wf.metrics_out_of_sample.total_return:.8f}",
                ]
            )
            rows.append(
                ["out_of_sample_sharpe", f"{wf.metrics_out_of_sample.sharpe:.8f}"]
            )
    return rows


def _equity_rows(run: BacktestResponse) -> list[list[str]]:
    rows = [["date", "equity", "cash", "drawdown_pct"]]
    for p in run.equity_curve:
        rows.append(
            [str(p.date), f"{p.equity:.6f}", f"{p.cash:.6f}", f"{p.drawdown_pct:.8f}"]
        )
    return rows


def _trades_rows(run: BacktestResponse) -> list[list[str]]:
    rows = [
        [
            "id",
            "symbol",
            "side",
            "qty",
            "price",
            "ts",
            "reason",
            "pnl",
            "pnl_pct",
            "note",
        ]
    ]
    for t in run.trades:
        side = t.side.value if hasattr(t.side, "value") else str(t.side)
        reason = t.reason.value if hasattr(t.reason, "value") else str(t.reason)
        rows.append(
            [
                t.id,
                t.symbol,
                side,
                f"{t.qty:.6f}",
                f"{t.price:.6f}",
                str(t.ts),
                reason,
                "" if t.pnl is None else f"{t.pnl:.6f}",
                "" if t.pnl_pct is None else f"{t.pnl_pct:.8f}",
                t.note or "",
            ]
        )
    return rows


def _mc_summary_rows(mc: MonteCarloResponse) -> list[list[str]]:
    r = mc.result
    d = r.terminal_return_dist
    return [
        ["key", "value"],
        ["monte_carlo_id", str(mc.id)],
        ["backtest_run_id", str(mc.backtest_run_id)],
        ["n_paths", str(r.n_paths)],
        ["horizon_days", str(r.horizon_days)],
        ["start_equity", f"{r.start_equity:.6f}"],
        ["block_bootstrap", str(r.block_bootstrap)],
        ["block_size", "" if r.block_size is None else str(r.block_size)],
        ["seed", "" if r.seed is None else str(r.seed)],
        ["terminal_mean", f"{d.mean:.8f}"],
        ["terminal_std", f"{d.std:.8f}"],
        ["terminal_p5", f"{d.p5:.8f}"],
        ["terminal_p50", f"{d.p50:.8f}"],
        ["terminal_p95", f"{d.p95:.8f}"],
        ["prob_below_start", f"{d.prob_below_start:.8f}"],
        ["assumptions", r.assumptions],
    ]


def _mc_bands_rows(mc: MonteCarloResponse) -> list[list[str]]:
    rows = [["day", "p5", "p25", "p50", "p75", "p95"]]
    for b in mc.result.percentile_bands:
        rows.append(
            [
                str(b.day),
                f"{b.p5:.6f}",
                f"{b.p25:.6f}",
                f"{b.p50:.6f}",
                f"{b.p75:.6f}",
                f"{b.p95:.6f}",
            ]
        )
    return rows


def _write_csv(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _zip_files(files: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return out.getvalue()


def build_backtest_csv_zip(
    run: BacktestResponse,
    monte_carlo: Optional[MonteCarloResponse] = None,
) -> bytes:
    """ZIP: metrics.csv, equity.csv, trades.csv, and MC CSVs when present."""
    files: dict[str, bytes] = {
        "metrics.csv": _write_csv(_metrics_rows(run)),
        "equity.csv": _write_csv(_equity_rows(run)),
        "trades.csv": _write_csv(_trades_rows(run)),
    }
    if monte_carlo is not None:
        files["mc_summary.csv"] = _write_csv(_mc_summary_rows(monte_carlo))
        files["mc_bands.csv"] = _write_csv(_mc_bands_rows(monte_carlo))
    return _zip_files(files)


def build_compare_csv_zip(runs: list[BacktestResponse]) -> bytes:
    """ZIP: compare_metrics.csv + per-strategy equity/trades."""
    header = [
        "strategy",
        "run_id",
        "total_return",
        "cagr",
        "volatility",
        "sharpe",
        "max_drawdown",
        "num_trades",
        "num_stop_losses",
        "num_dd_halts",
        "final_equity",
        "excess_return",
        "excess_sharpe",
    ]
    rows: list[list[str]] = [header]
    files: dict[str, bytes] = {}
    for run in runs:
        m = run.metrics
        strat = run.request.strategy.type
        rows.append(
            [
                strat,
                str(run.id),
                "" if m is None else f"{m.total_return:.8f}",
                "" if m is None else f"{m.cagr:.8f}",
                "" if m is None else f"{m.volatility:.8f}",
                "" if m is None else f"{m.sharpe:.8f}",
                "" if m is None else f"{m.max_drawdown:.8f}",
                "" if m is None else str(m.num_trades),
                "" if m is None else str(m.num_stop_losses),
                "" if m is None else str(m.num_dd_halts),
                "" if m is None else f"{m.final_equity:.6f}",
                ""
                if not run.benchmark or run.benchmark.excess_return is None
                else f"{run.benchmark.excess_return:.8f}",
                ""
                if not run.benchmark or run.benchmark.excess_sharpe is None
                else f"{run.benchmark.excess_sharpe:.8f}",
            ]
        )
        files[f"equity_{strat}.csv"] = _write_csv(_equity_rows(run))
        files[f"trades_{strat}.csv"] = _write_csv(_trades_rows(run))
        files[f"metrics_{strat}.csv"] = _write_csv(_metrics_rows(run))
    files["compare_metrics.csv"] = _write_csv(rows)
    return _zip_files(files)
