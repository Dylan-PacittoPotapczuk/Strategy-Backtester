"""Bootstrap / block-bootstrap Monte Carlo forward projections.

Takes an empirical daily return series from a completed backtest and
resamples paths of length ``horizon_days``. Percentile equity bands and a
terminal return summary are returned. Path-dependent guardrails are NOT
re-applied on synthetic paths (MVP assumption — disclose in the UI).
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from app.models.schemas import (
    MonteCarloRequest,
    MonteCarloResult,
    PercentileBand,
    TerminalReturnDist,
)

# Cap defaults for snappy UX; API also enforces max on request models.
DEFAULT_N_PATHS = 500
MAX_N_PATHS = 2000
DEFAULT_HORIZON = 252
DEFAULT_BLOCK_SIZE = 10


def _sample_indices(
    n_obs: int,
    n_paths: int,
    horizon: int,
    *,
    block_bootstrap: bool,
    block_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return index matrix shaped (n_paths, horizon) into the return series."""
    if n_obs < 1:
        raise ValueError("daily_returns must contain at least one observation")
    if horizon < 1:
        raise ValueError("horizon_days must be >= 1")
    if n_paths < 1:
        raise ValueError("n_paths must be >= 1")

    if not block_bootstrap:
        return rng.integers(0, n_obs, size=(n_paths, horizon))

    bs = max(1, min(block_size, n_obs))
    # Number of blocks needed to cover the horizon (may overshoot; trim later).
    n_blocks = int(np.ceil(horizon / bs))
    # Valid block starts: 0 .. n_obs - bs (inclusive). If series shorter than
    # one block, fall back to wrapping via modulo on the drawn indices.
    if n_obs >= bs:
        starts = rng.integers(0, n_obs - bs + 1, size=(n_paths, n_blocks))
        offsets = np.arange(bs)
        # (n_paths, n_blocks, bs)
        blocks = starts[..., None] + offsets
        flat = blocks.reshape(n_paths, n_blocks * bs)
        return flat[:, :horizon]

    # Short series: iid with wrap via modulo after drawing.
    raw = rng.integers(0, n_obs, size=(n_paths, horizon))
    return raw


def run_monte_carlo(
    daily_returns: list[float] | np.ndarray,
    request: MonteCarloRequest,
    *,
    start_equity: float,
) -> MonteCarloResult:
    """Simulate equity paths from empirical returns and summarize percentiles."""
    returns = np.asarray(daily_returns, dtype=np.float64)
    if returns.ndim != 1:
        raise ValueError("daily_returns must be a 1-D series")
    if len(returns) < 1:
        raise ValueError("Cannot run Monte Carlo without daily returns from the backtest")
    if not np.isfinite(returns).all():
        raise ValueError("daily_returns contain non-finite values")
    if start_equity <= 0:
        raise ValueError("start_equity must be > 0")

    n_paths = request.n_paths
    horizon = request.horizon_days
    seed = request.seed if request.seed is not None else None
    rng = np.random.default_rng(seed)

    idx = _sample_indices(
        len(returns),
        n_paths,
        horizon,
        block_bootstrap=request.block_bootstrap,
        block_size=request.block_size,
        rng=rng,
    )
    sampled = returns[idx]  # (n_paths, horizon)
    # Equity path: start at start_equity, compound daily returns.
    growth = np.cumprod(1.0 + sampled, axis=1)
    equity = start_equity * growth  # (n_paths, horizon)

    percentiles = (5, 25, 50, 75, 95)
    band_vals = np.percentile(equity, percentiles, axis=0)  # (5, horizon)

    bands: list[PercentileBand] = []
    for day in range(horizon):
        bands.append(
            PercentileBand(
                day=day + 1,
                p5=float(band_vals[0, day]),
                p25=float(band_vals[1, day]),
                p50=float(band_vals[2, day]),
                p75=float(band_vals[3, day]),
                p95=float(band_vals[4, day]),
            )
        )

    terminal = equity[:, -1]
    terminal_returns = terminal / start_equity - 1.0
    term_pcts = np.percentile(terminal_returns, (5, 50, 95))
    prob_loss = float(np.mean(terminal_returns < 0.0))

    terminal_dist = TerminalReturnDist(
        mean=float(np.mean(terminal_returns)),
        std=float(np.std(terminal_returns, ddof=1)) if n_paths > 1 else 0.0,
        p5=float(term_pcts[0]),
        p50=float(term_pcts[1]),
        p95=float(term_pcts[2]),
        prob_below_start=prob_loss,
    )

    # Thin sample of paths for optional charting (cap to keep payload small).
    sample_n = min(request.paths_sample_count, n_paths)
    paths_sample: Optional[list[list[float]]] = None
    if sample_n > 0:
        # Deterministic subset: first sample_n paths (RNG already fixed order).
        paths_sample = equity[:sample_n].tolist()

    return MonteCarloResult(
        percentile_bands=bands,
        terminal_return_dist=terminal_dist,
        paths_sample=paths_sample,
        start_equity=float(start_equity),
        n_paths=n_paths,
        horizon_days=horizon,
        block_bootstrap=request.block_bootstrap,
        block_size=request.block_size if request.block_bootstrap else None,
        seed=seed,
        assumptions=(
            "Forward paths resample the backtest's daily returns after costs and "
            "guardrails. Path-dependent risk rules (stops, drawdown halts) are not "
            "re-applied on each synthetic path; bands assume similar risk-constrained "
            "behavior continues."
        ),
    )
