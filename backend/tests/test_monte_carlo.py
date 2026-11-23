"""Monte Carlo sampler: seed determinism and percentile band shape."""

from __future__ import annotations

import numpy as np
import pytest

from app.engine.monte_carlo import run_monte_carlo
from app.models.schemas import MonteCarloRequest


def _fixed_returns(n: int = 60) -> list[float]:
    # Mix of modest up/down days so bands have width.
    rng = np.random.default_rng(0)
    return (rng.normal(0.0005, 0.01, size=n)).tolist()


def test_seed_determinism_iid() -> None:
    returns = _fixed_returns()
    req = MonteCarloRequest(
        n_paths=200,
        horizon_days=63,
        seed=42,
        block_bootstrap=False,
        paths_sample_count=3,
    )
    a = run_monte_carlo(returns, req, start_equity=100_000.0)
    b = run_monte_carlo(returns, req, start_equity=100_000.0)

    assert a.n_paths == 200
    assert a.horizon_days == 63
    assert len(a.percentile_bands) == 63
    assert a.paths_sample is not None and len(a.paths_sample) == 3

    for ba, bb in zip(a.percentile_bands, b.percentile_bands, strict=True):
        assert ba.day == bb.day
        assert ba.p5 == pytest.approx(bb.p5)
        assert ba.p25 == pytest.approx(bb.p25)
        assert ba.p50 == pytest.approx(bb.p50)
        assert ba.p75 == pytest.approx(bb.p75)
        assert ba.p95 == pytest.approx(bb.p95)

    assert a.terminal_return_dist.mean == pytest.approx(b.terminal_return_dist.mean)
    assert a.terminal_return_dist.p50 == pytest.approx(b.terminal_return_dist.p50)
    assert a.paths_sample == b.paths_sample


def test_different_seeds_diverge() -> None:
    returns = _fixed_returns()
    a = run_monte_carlo(
        returns,
        MonteCarloRequest(n_paths=150, horizon_days=40, seed=1),
        start_equity=50_000.0,
    )
    b = run_monte_carlo(
        returns,
        MonteCarloRequest(n_paths=150, horizon_days=40, seed=2),
        start_equity=50_000.0,
    )
    assert a.percentile_bands[-1].p50 != pytest.approx(b.percentile_bands[-1].p50, abs=1e-12)


def test_band_ordering_each_day() -> None:
    returns = _fixed_returns(80)
    result = run_monte_carlo(
        returns,
        MonteCarloRequest(n_paths=400, horizon_days=50, seed=7),
        start_equity=100_000.0,
    )
    for band in result.percentile_bands:
        assert band.p5 <= band.p25 <= band.p50 <= band.p75 <= band.p95
        assert band.day >= 1


def test_terminal_dist_bounds() -> None:
    returns = _fixed_returns()
    result = run_monte_carlo(
        returns,
        MonteCarloRequest(n_paths=300, horizon_days=30, seed=9),
        start_equity=10_000.0,
    )
    d = result.terminal_return_dist
    assert d.p5 <= d.p50 <= d.p95
    assert 0.0 <= d.prob_below_start <= 1.0
    assert d.std >= 0.0
    assert "not re-applied" in result.assumptions.lower() or "not" in result.assumptions.lower()


def test_block_bootstrap_determinism_and_shape() -> None:
    returns = _fixed_returns(100)
    req = MonteCarloRequest(
        n_paths=250,
        horizon_days=45,
        seed=11,
        block_bootstrap=True,
        block_size=5,
    )
    a = run_monte_carlo(returns, req, start_equity=25_000.0)
    b = run_monte_carlo(returns, req, start_equity=25_000.0)
    assert a.block_bootstrap is True
    assert a.block_size == 5
    assert a.percentile_bands[-1].p50 == pytest.approx(b.percentile_bands[-1].p50)
    for band in a.percentile_bands:
        assert band.p5 <= band.p95


def test_constant_returns_collapse_bands() -> None:
    """If every day returns the same amount, all percentiles coincide."""
    returns = [0.001] * 40
    result = run_monte_carlo(
        returns,
        MonteCarloRequest(n_paths=100, horizon_days=20, seed=3),
        start_equity=1_000.0,
    )
    last = result.percentile_bands[-1]
    expected = 1_000.0 * ((1.001) ** 20)
    assert last.p5 == pytest.approx(expected, rel=1e-9)
    assert last.p50 == pytest.approx(expected, rel=1e-9)
    assert last.p95 == pytest.approx(expected, rel=1e-9)


def test_empty_returns_raises() -> None:
    with pytest.raises(ValueError, match="daily returns"):
        run_monte_carlo(
            [],
            MonteCarloRequest(n_paths=10, horizon_days=5, seed=1),
            start_equity=1_000.0,
        )
