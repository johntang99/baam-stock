"""DP 1.16 one-click pipeline + CLI (AC-34 Phase 1 part; MP §3 B; OQ-50). SYNTHETIC data."""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from sr.cli import main
from sr.forecast.run import forecast_snapshot
from sr.pipeline import orchestrator as orch
from sr.pipeline.orchestrator import RunContext, run_pipeline
from sr.timeguard import LookaheadError
from tests.test_dataset import PEERS_ALL, REFS, FrameProvider, synthetic_quotes
from tests.test_forecast import NVDA, SLOT, history, models

TARGETS = ["regular_60m", "regular_60m_move"]


@pytest.fixture(scope="module")
def provider() -> FrameProvider:
    return FrameProvider(synthetic_quotes([NVDA, *PEERS_ALL, *REFS], seed=21))


class Guarded:
    """Point-in-time wrapper: refuses any request ending after its as_of (like FixtureProvider(as_of=…))."""

    def __init__(self, inner, as_of: datetime) -> None:  # type: ignore[no-untyped-def]
        self.inner, self.as_of, self.security_ids = inner, as_of, inner.security_ids

    def quotes_1s(self, ids: list[str], start: datetime, end: datetime) -> pd.DataFrame:
        if end > self.as_of:
            raise LookaheadError(f"requested data up to {end} after provider as_of {self.as_of}")
        return self.inner.quotes_1s(ids, start, end)

    def get_official_close(self, sid: str, d):  # type: ignore[no-untyped-def]
        return None


def ctx(conn, provider, tmp_path, as_of: datetime = SLOT, sources=None) -> RunContext:  # type: ignore[no-untyped-def]
    m = models(conn, tmp_path)
    p = Guarded(provider, as_of)
    q = provider.quotes_1s([NVDA], as_of - timedelta(minutes=30), as_of)
    closes = {
        sid: float((g["bid"].iloc[0] + g["ask"].iloc[0]) / 2)
        for sid, g in provider.quotes_1s(list(provider.security_ids), as_of - timedelta(minutes=25), as_of)
        .sort_values("ts")
        .groupby("security_id")
    }
    assert len(q)
    return RunContext(p, m, history(), sources=sources or [], prev_close=closes, feature_dir=tmp_path)


def count(conn, table: str) -> int:  # type: ignore[no-untyped-def]
    return int(conn.execute(f"select count(*) as n from {table}").fetchone()["n"])


def test_ac34_replay_runs_eight_steps(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = ctx(conn, provider, tmp_path)
    res = run_pipeline(conn, [NVDA], TARGETS, "replay", SLOT, c)
    assert res.status in ("succeeded", "partial")
    steps = conn.execute(
        "select * from pipeline_run_steps where pipeline_run_id = %s order by step_no", (res.pipeline_run_id,)
    ).fetchall()
    assert [s["step"] for s in steps] == list(orch.STEPS)
    assert [s["status"] for s in steps] == [
        "skipped",
        "skipped",
        "skipped",
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded",
        "succeeded",
    ]
    run = conn.execute(
        "select * from pipeline_runs where pipeline_run_id = %s", (res.pipeline_run_id,)
    ).fetchone()
    assert (
        run["mode"] == "replay"
        and run["outputs"]["snapshot_ids"]
        and len(run["outputs"]["prediction_ids"]) == 2
    )
    preds = conn.execute("select * from predictions").fetchall()
    assert {p["sampling_rule"] for p in preds} == {"on_demand"}  # trigger on_demand: never primary
    assert not any(p["is_primary"] for p in preds)
    jobs = conn.execute("select * from jobs where job_type = 'settle_due'").fetchall()
    assert {j["payload"]["prediction_id"] for j in jobs} == {
        p["prediction_id"] for p in preds if p["status"] == "published"
    }
    # the same result as calling the steps one by one (AC-34: "与逐步回放一致")
    again = forecast_snapshot(
        conn,
        run["outputs"]["snapshot_ids"][0],
        c.provider,
        c.models,
        c.history,
        SLOT + c.publish_lag,
        feature_dir=tmp_path,
        publish_now=False,
    )
    by_row = {p["target_row_id"]: p for p in preds}
    for p in again.predictions:
        assert p["probabilities"] == by_row[p["target_row_id"]]["probabilities"]
        assert p["move_quantiles"] == by_row[p["target_row_id"]]["move_quantiles"]


def test_reuse_when_inputs_are_unchanged(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = ctx(conn, provider, tmp_path)
    first = run_pipeline(conn, [NVDA], TARGETS, "replay", SLOT, c)
    same = run_pipeline(
        conn, [NVDA], TARGETS, "replay", SLOT, c
    )  # identical request: the run itself is returned
    assert same.reused_run and same.pipeline_run_id == first.pipeline_run_id
    other = run_pipeline(
        conn, [NVDA], TARGETS, "replay", SLOT, c, requested_by="usr_b"
    )  # new run, same watermarks
    assert other.outputs["reused"] is True and count(conn, "predictions") == 2
    assert sorted(other.outputs["prediction_ids"]) == sorted(first.outputs["prediction_ids"])
    infer = next(s for s in other.steps if s["step"] == "infer")
    assert infer["status"] == "skipped" and infer["detail"]["reason"] == "inputs_unchanged"


def test_force_recompute_publishes_on_demand_copies(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = ctx(conn, provider, tmp_path)
    run_pipeline(conn, [NVDA], TARGETS, "replay", SLOT, c)
    forced = run_pipeline(
        conn, [NVDA], TARGETS, "replay", SLOT, c, requested_by="usr_r", reuse_policy="force_recompute"
    )
    assert forced.outputs["reused"] is False and count(conn, "predictions") == 4
    new = conn.execute(
        "select * from predictions where prediction_id = any(%s)", (forced.outputs["prediction_ids"],)
    ).fetchall()
    assert {p["sampling_rule"] for p in new} == {"on_demand"} and not any(p["is_primary"] for p in new)


def test_dry_run_writes_only_the_report(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = ctx(conn, provider, tmp_path)
    before = {
        t: count(conn, t)
        for t in ("predictions", "prediction_runs", "security_state_snapshots", "reference_quotes", "jobs")
    }
    res = run_pipeline(conn, [NVDA], TARGETS, "dry_run", SLOT, c)
    assert {
        t: count(conn, t) for t in before
    } == before  # AC-34: dry_run does not write predictions (or anything else)
    run = conn.execute(
        "select * from pipeline_runs where pipeline_run_id = %s", (res.pipeline_run_id,)
    ).fetchone()
    assert (
        run["mode"] == "dry_run" and len(run["outputs"]["prediction_ids"]) == 2
    )  # would-be forecasts in the report
    steps = conn.execute(
        "select step, status, detail from pipeline_run_steps where pipeline_run_id = %s order by step_no",
        (res.pipeline_run_id,),
    ).fetchall()
    assert len(steps) == 8 and steps[6]["status"] == "skipped" and steps[6]["detail"]["reason"] == "dry_run"


def test_failure_then_resume(conn, provider, tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    c = ctx(conn, provider, tmp_path)
    real = orch.forecast_snapshot
    calls = {"n": 0}

    def flaky(*a, **k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("model server unavailable (synthetic)")
        return real(*a, **k)

    monkeypatch.setattr(orch, "forecast_snapshot", flaky)
    bad = run_pipeline(conn, [NVDA], TARGETS, "replay", SLOT, c)
    assert bad.status == "failed" and count(conn, "predictions") == 0
    st = {
        s["step"]: s
        for s in conn.execute(
            "select * from pipeline_run_steps where pipeline_run_id = %s", (bad.pipeline_run_id,)
        ).fetchall()
    }
    assert st["infer"]["status"] == "failed" and st["infer"]["error"]["code"] == "RuntimeError"
    assert st["build_snapshot"]["status"] == "succeeded"
    good = run_pipeline(conn, [NVDA], TARGETS, "replay", SLOT, c)  # same request: resume
    assert good.pipeline_run_id == bad.pipeline_run_id and good.status in ("succeeded", "partial")
    st2 = {
        s["step"]: s
        for s in conn.execute(
            "select * from pipeline_run_steps where pipeline_run_id = %s", (bad.pipeline_run_id,)
        ).fetchall()
    }
    assert (
        st2["infer"]["attempt"] == 2 and st2["build_snapshot"]["attempt"] == 1
    )  # the snapshot step was not redone
    assert count(conn, "security_state_snapshots") == 1 and count(conn, "predictions") == 2


def test_collection_step_with_sources(conn, provider, tmp_path, doc_storage) -> None:  # type: ignore[no-untyped-def]
    from tests.test_collection_reasoning import scenario

    sources, _ = scenario(conn)
    c = ctx(conn, provider, tmp_path, sources=sources)
    c.storage = doc_storage
    res = run_pipeline(conn, [NVDA], TARGETS, "replay", SLOT, c)
    collect, verify = res.steps[0], res.steps[1]
    assert collect["status"] == "succeeded" and collect["detail"]["collection_run_id"]
    assert verify["status"] == "succeeded" and verify["detail"]["duplicate"] >= 1


def test_provider_refusing_future_data_fails_the_step(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = ctx(conn, provider, tmp_path)
    c.provider = Guarded(provider, SLOT - timedelta(minutes=5))  # the provider only knows data up to 09:55 ET
    res = run_pipeline(conn, [NVDA], TARGETS, "replay", SLOT, c)
    snap = next(s for s in res.steps if s["step"] == "build_snapshot")
    assert res.status == "failed" and snap["status"] == "failed" and snap["error"]["code"] == "LookaheadError"
    assert count(conn, "predictions") == 0


def test_cli_requires_mode_and_rejects_unknown_targets(conn, provider, tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SystemExit):
        main(["run", "--security", "sec_nvda", "--as-of", "2026-12-10T15:00:00Z", "--fixture", "x.parquet"])
    with pytest.raises(ValueError, match="not built yet"):
        run_pipeline(conn, [NVDA], ["overnight_gap"], "replay", SLOT, ctx(conn, provider, tmp_path))


def test_ac34_the_cli_command_itself(conn, db_url, fixture_path, tmp_path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    """`uv run sr run --security sec_nvda --targets regular_60m,regular_60m_move --mode replay --as-of <ts>` runs the
    8 steps; `--mode dry_run` writes no predictions (AC-34, Phase 1 part). Synthetic fixture."""
    import json

    models(conn, tmp_path)  # registers a market_logit + gbdt and a regular_60m dataset (window history)
    monkeypatch.setenv("DIRECT_URL", db_url)
    monkeypatch.chdir(tmp_path)  # feature rows land under the temp dir
    args = [
        "run",
        "--security",
        "sec_nvda",
        "--targets",
        "regular_60m,regular_60m_move",
        "--fixture",
        str(fixture_path),
    ]
    assert main([*args, "--mode", "replay", "--as-of", "2026-12-01T15:00:00Z"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [s[1] for s in out["steps"]] == list(orch.STEPS)
    run = conn.execute(
        "select * from pipeline_runs where pipeline_run_id = %s", (out["pipeline_run_id"],)
    ).fetchone()
    assert run["mode"] == "replay" and count(conn, "pipeline_run_steps") == 8
    n_pred = count(conn, "predictions")
    assert n_pred == 2  # one per target (abstained here: the fixture has no previous close)
    assert main([*args, "--mode", "dry_run", "--as-of", "2026-12-01T15:05:00Z"]) == 0
    dry = json.loads(capsys.readouterr().out)
    assert count(conn, "predictions") == n_pred  # dry_run writes no predictions
    assert (
        conn.execute(
            "select mode from pipeline_runs where pipeline_run_id = %s", (dry["pipeline_run_id"],)
        ).fetchone()["mode"]
        == "dry_run"
    )
