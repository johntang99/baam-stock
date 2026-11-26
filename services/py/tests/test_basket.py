"""AC-05: basket returns vs hand calculations (< 1e-9) and the missing rule (D-06, D-08)."""

import pytest

from sr.benchmark.basket import basket_return, equal_weights, relative_return_pp


def test_hand_example_1_equal_weight_three() -> None:
    w = equal_weights(["a", "b", "c"])
    r = basket_return({"a": 100, "b": 50, "c": 20}, {"a": 101, "b": 49, "c": 20.4}, w)
    # returns +1%, -2%, +2% -> mean 1/3 %
    assert r.status == "ok" and abs(r.return_pct - (1 - 2 + 2) / 3) < 1e-9  # type: ignore[operator]


def test_hand_example_2_custom_weights() -> None:
    w = {"a": 0.5, "b": 0.3, "c": 0.2}
    r = basket_return({"a": 200, "b": 80, "c": 10}, {"a": 203, "b": 79.2, "c": 10.05}, w)
    # 0.5*1.5% + 0.3*(-1%) + 0.2*0.5% = 0.75 - 0.3 + 0.1 = 0.55%
    assert abs(r.return_pct - 0.55) < 1e-9  # type: ignore[operator]


def test_hand_example_3_eleven_with_one_missing_renormalised() -> None:
    names = [f"c{i}" for i in range(11)]
    w = equal_weights(names)
    start = {n: 100.0 for n in names}
    end = {n: 100.0 + i * 0.1 for i, n in enumerate(names)}  # returns 0.0%, 0.1%, ..., 1.0%
    end["c10"] = None  # one missing -> mean of first 10 = 0.45%
    r = basket_return(start, end, w)
    assert r.status == "ok" and r.missing == ("c10",)
    assert abs(r.return_pct - 0.45) < 1e-9  # type: ignore[operator]
    assert abs(sum(r.weights_used.values()) - 1) < 1e-12


def test_two_missing_is_unavailable() -> None:
    names = [f"c{i}" for i in range(11)]
    start = {n: 100.0 for n in names}
    end = {n: 101.0 for n in names} | {"c0": None, "c1": float("nan")}
    r = basket_return(start, end, equal_weights(names))
    assert r.status == "benchmark_unavailable" and r.return_pct is None and set(r.missing) == {"c0", "c1"}
    assert relative_return_pp(0.5, r) is None


def test_relative_return() -> None:
    r = basket_return({"a": 100}, {"a": 100.18}, {"a": 1.0})
    assert relative_return_pp(0.42, r) == pytest.approx(0.24, abs=1e-9)  # DC §8.1: 0.42 − 0.18
    # AC-10 sanity: stock −1%, basket −3% -> +2pp
    r2 = basket_return({"a": 100}, {"a": 97}, {"a": 1.0})
    assert relative_return_pp(-1.0, r2) == pytest.approx(2.0, abs=1e-9)
