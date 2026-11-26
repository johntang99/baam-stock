"""Scoring: DC §8.1 Brier / pinball examples, AC-28 BSS, references, day-block bootstrap."""

import numpy as np
import pytest

from sr.eval.bootstrap import block_bootstrap, paired_block_bootstrap, resample_indices
from sr.eval.metrics import (
    always_flat_forecast,
    brier,
    brier_skill_score,
    class_frequency_forecast,
    coverage,
    hit,
    mean_brier,
    persistence_forecast,
    pinball_by_quantile,
    pinball_loss,
    quantile_hits,
)

P = {"outperform": 0.38, "flat": 0.35, "underperform": 0.27}


def test_brier_dc81_example() -> None:
    assert brier(P, "outperform") == pytest.approx(0.5798, abs=1e-12)
    assert hit(P, "outperform")
    u = {"outperform": 1 / 3, "flat": 1 / 3, "underperform": 1 / 3}
    assert brier(u, "flat") == pytest.approx(2 / 3)


def test_brier_rejects_bad_probabilities() -> None:
    with pytest.raises(ValueError):
        brier({"outperform": 0.5, "flat": 0.5, "underperform": 0.1}, "flat")
    with pytest.raises(ValueError):
        brier({"outperform": 0.5, "flat": 0.5}, "flat")


def test_pinball_dc81_example() -> None:
    q = {"p50": 0.31, "p80": 0.58, "p90": 0.77}
    pl = pinball_by_quantile(q, 0.24)
    assert (
        pl["p50"] == pytest.approx(0.035)
        and pl["p80"] == pytest.approx(0.068)
        and pl["p90"] == pytest.approx(0.053)
    )
    assert quantile_hits(q, 0.24) == {"p50": True, "p80": True, "p90": True}
    assert pinball_loss(0.9, 0.5, 1.0) == pytest.approx(0.45)  # under-prediction side
    assert coverage([True, False, True, True]) == 0.75


def test_bss_ac28() -> None:
    assert brier_skill_score(0.641, 0.666) == pytest.approx(0.0375375, abs=1e-6)
    assert brier_skill_score(0.666, 0.666) == 0.0


def test_reference_forecasts() -> None:
    cf = class_frequency_forecast(["outperform", "flat", "flat", "underperform"])
    assert cf == {"outperform": 0.25, "flat": 0.5, "underperform": 0.25}
    assert brier(always_flat_forecast(), "flat") == 0 and brier(always_flat_forecast(), "outperform") == 2
    assert persistence_forecast("underperform")["underperform"] == 1.0
    outcomes = ["outperform", "flat", "underperform", "flat"]
    model = [P] * 4
    ref = [cf] * 4
    bss = brier_skill_score(mean_brier(model, outcomes), mean_brier(ref, outcomes))
    assert np.isfinite(bss)


def test_bootstrap_reproducible_with_fixed_seed() -> None:
    rng = np.random.default_rng(0)
    vals = rng.normal(size=120)
    days = np.repeat(np.arange(20), 6)
    a = block_bootstrap(vals, days, seed=7)
    b = block_bootstrap(vals, days, seed=7)
    assert a.n_resamples == 2000 and a.n_blocks == 20
    assert np.array_equal(a.samples, b.samples) and (a.ci_low, a.ci_high) == (b.ci_low, b.ci_high)
    assert not np.array_equal(a.samples, block_bootstrap(vals, days, seed=8).samples)
    assert a.ci_low < a.estimate < a.ci_high


def test_bootstrap_resamples_whole_days() -> None:
    days = ["d1"] * 3 + ["d2"] * 5 + ["d3"] * 2
    rng = np.random.default_rng(1)
    for _ in range(200):
        idx = resample_indices(days, rng)
        picked = [days[i] for i in idx]
        for d, size in (("d1", 3), ("d2", 5), ("d3", 2)):
            assert picked.count(d) % size == 0  # a day is always taken as a whole block


def test_bootstrap_constant_within_day_only_takes_day_means() -> None:
    # if each day's values are constant, every resample mean is a weighted mean of day values
    vals = [1.0] * 4 + [3.0] * 4
    days = [0] * 4 + [1] * 4
    r = block_bootstrap(vals, days, seed=3, n_resamples=500)
    assert set(np.round(r.samples, 9)) <= {1.0, 2.0, 3.0}


def test_paired_bootstrap() -> None:
    c = [0.60, 0.62, 0.64, 0.61] * 5
    k = [0.65, 0.66, 0.66, 0.64] * 5
    days = np.repeat(np.arange(5), 4)
    r = paired_block_bootstrap(c, k, days, seed=11)
    assert r.estimate == pytest.approx(-0.035) and r.ci_high < 0
