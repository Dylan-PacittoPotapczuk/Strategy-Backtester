"""Simple PDF risk-report summaries (reportlab)."""

from __future__ import annotations

import io
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.schemas import BacktestResponse, MonteCarloResponse

ASSUMPTIONS_TEXT = (
    "Fills use the next open after a signal (no same-bar look-ahead). "
    "Default costs are ~5 bps slippage and $0 commission unless overridden. "
    "Prices are free Yahoo Finance end-of-day (adjusted). "
    "Long-only equities/ETFs in USD. "
    "Portfolio drawdown breach halts new buys; positions are not auto-flattened by default. "
    "Monte Carlo (when included) bootstraps backtest daily returns and does not re-apply "
    "path-dependent stop or drawdown rules on each synthetic path."
)


def _pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def _usd(x: float) -> str:
    return f"${x:,.2f}"


def _num(x: float) -> str:
    return f"{x:.3f}"


def _styles():
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "ReportTitle",
        parent=base["Heading1"],
        fontSize=16,
        spaceAfter=8,
        textColor=colors.HexColor("#14201c"),
    )
    h2 = ParagraphStyle(
        "ReportH2",
        parent=base["Heading2"],
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor("#0f6e56"),
    )
    body = ParagraphStyle(
        "ReportBody",
        parent=base["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#24302c"),
    )
    small = ParagraphStyle(
        "ReportSmall",
        parent=base["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#5a6b63"),
    )
    return title, h2, body, small


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    data = [[k, v] for k, v in rows]
    t = Table(data, colWidths=[2.4 * inch, 4.4 * inch])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#24302c")),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f4f7f5"), colors.white]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _draw_equity_chart(canvas_obj, run: BacktestResponse, x: float, y: float, w: float, h: float) -> None:
    """Draw a simple equity polyline on the canvas (absolute coords)."""
    pts = run.equity_curve
    if len(pts) < 2:
        return
    equities = [p.equity for p in pts]
    lo, hi = min(equities), max(equities)
    span = hi - lo or 1.0
    canvas_obj.setStrokeColor(colors.HexColor("#0f6e56"))
    canvas_obj.setLineWidth(1.5)
    canvas_obj.setFillColor(colors.HexColor("#eef5f1"))
    canvas_obj.rect(x, y, w, h, stroke=0, fill=1)
    canvas_obj.setStrokeColor(colors.HexColor("#c5d4cc"))
    canvas_obj.rect(x, y, w, h, stroke=1, fill=0)
    n = len(equities)
    path = canvas_obj.beginPath()
    for i, eq in enumerate(equities):
        px = x + (i / (n - 1)) * w
        py = y + ((eq - lo) / span) * (h - 4) + 2
        if i == 0:
            path.moveTo(px, py)
        else:
            path.lineTo(px, py)
    canvas_obj.setStrokeColor(colors.HexColor("#0f6e56"))
    canvas_obj.drawPath(path, stroke=1, fill=0)
    canvas_obj.setFillColor(colors.HexColor("#5a6b63"))
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.drawString(x + 4, y + h - 10, f"Equity {_usd(equities[0])} → {_usd(equities[-1])}")


def _build_run_story(run: BacktestResponse, monte_carlo: Optional[MonteCarloResponse], styles):
    title, h2, body, small = styles
    req = run.request
    m = run.metrics
    story = []
    label = run.name or req.strategy.type.replace("_", " ").title()
    story.append(Paragraph(f"Risk report — {label}", title))
    story.append(
        Paragraph(
            f"{req.strategy.type} · {', '.join(req.symbols)} · "
            f"{req.start_date} → {req.end_date} · run {run.id}",
            small,
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("Key metrics", h2))
    metric_rows: list[tuple[str, str]] = [
        ("Starting cash", _usd(req.initial_cash)),
    ]
    if m is not None:
        metric_rows.extend(
            [
                ("Ending value", _usd(m.final_equity)),
                ("Total return", _pct(m.total_return)),
                ("Avg yearly return (CAGR)", _pct(m.cagr)),
                ("Risk-adjusted return (Sharpe)", _num(m.sharpe)),
                ("Worst drop (max drawdown)", _pct(m.max_drawdown)),
                ("Day-to-day swings (vol)", _pct(m.volatility)),
                ("Filled trades", str(m.num_trades)),
                ("Loss-limit sells", str(m.num_stop_losses)),
                ("Drop-limit pauses", str(m.num_dd_halts)),
            ]
        )
    if run.benchmark and run.benchmark.enabled and run.benchmark.excess_return is not None:
        metric_rows.append(
            (f"Excess return vs {run.benchmark.symbol}", _pct(run.benchmark.excess_return))
        )
    story.append(_kv_table(metric_rows))

    story.append(Paragraph("Risk & cost settings", h2))
    story.append(
        _kv_table(
            [
                ("Position size limit", _pct(req.guardrails.max_position_pct)),
                ("Per-trade loss limit", _pct(req.guardrails.max_trade_loss_pct)),
                ("Portfolio drop limit", _pct(req.guardrails.max_portfolio_drawdown_pct)),
                ("Sizing mode", req.guardrails.sizing_mode),
                ("Slippage", f"{req.costs.slippage_bps:g} bps"),
                ("Commission / trade", _usd(req.costs.commission_per_trade)),
                ("Drawdown halt triggered", "Yes" if run.dd_halted else "No"),
            ]
        )
    )

    if monte_carlo is not None:
        r = monte_carlo.result
        d = r.terminal_return_dist
        story.append(Paragraph("Monte Carlo summary", h2))
        story.append(
            _kv_table(
                [
                    ("Paths", str(r.n_paths)),
                    ("Horizon (trading days)", str(r.horizon_days)),
                    ("Start equity", _usd(r.start_equity)),
                    ("Block bootstrap", "Yes" if r.block_bootstrap else "No"),
                    ("Terminal mean return", _pct(d.mean)),
                    ("Terminal median (p50)", _pct(d.p50)),
                    ("Terminal p5 / p95", f"{_pct(d.p5)} / {_pct(d.p95)}"),
                    ("Chance below start", _pct(d.prob_below_start)),
                ]
            )
        )
        story.append(Spacer(1, 4))
        story.append(Paragraph(r.assumptions, small))

    story.append(Paragraph("Assumptions", h2))
    story.append(Paragraph(ASSUMPTIONS_TEXT, body))
    return story


def build_backtest_pdf(
    run: BacktestResponse,
    monte_carlo: Optional[MonteCarloResponse] = None,
) -> bytes:
    buf = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=f"Risk report {run.id}",
    )
    story = _build_run_story(run, monte_carlo, styles)

    # Reserve space for equity chart via a flowable spacer; draw in onFirstPage
    story.insert(2, Spacer(1, 2.1 * inch))

    def _on_page(canvas_obj, _doc):
        canvas_obj.saveState()
        _draw_equity_chart(
            canvas_obj,
            run,
            x=0.7 * inch,
            y=letter[1] - 3.15 * inch,
            w=7.1 * inch,
            h=1.85 * inch,
        )
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=_on_page)
    return buf.getvalue()


def build_compare_pdf(runs: list[BacktestResponse]) -> bytes:
    buf = io.BytesIO()
    title, h2, body, small = _styles()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="Compare risk report",
    )
    story = []
    story.append(Paragraph("Compare — risk report", title))
    if runs:
        req = runs[0].request
        story.append(
            Paragraph(
                f"{', '.join(req.symbols)} · {req.start_date} → {req.end_date} · "
                f"start {_usd(req.initial_cash)}",
                small,
            )
        )
    story.append(Spacer(1, 8))
    story.append(Paragraph("Side-by-side metrics", h2))

    header = ["Strategy", "Return", "Sharpe", "Max DD", "Trades", "Stops", "DD halts"]
    data = [header]
    for run in runs:
        m = run.metrics
        data.append(
            [
                run.request.strategy.type.replace("_", " "),
                "—" if m is None else _pct(m.total_return),
                "—" if m is None else _num(m.sharpe),
                "—" if m is None else _pct(m.max_drawdown),
                "—" if m is None else str(m.num_trades),
                "—" if m is None else str(m.num_stop_losses),
                "—" if m is None else str(m.num_dd_halts),
            ]
        )
    table = Table(data, colWidths=[1.5 * inch, 0.9 * inch, 0.8 * inch, 0.9 * inch, 0.7 * inch, 0.7 * inch, 0.8 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f6e56")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f4f7f5"), colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c5d4cc")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Paragraph("Assumptions", h2))
    story.append(Paragraph(ASSUMPTIONS_TEXT, body))
    doc.build(story)
    return buf.getvalue()
