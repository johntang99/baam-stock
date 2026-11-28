"""DP 1.17 day replay + line-by-line verification report (Phase 1 acceptance: any prediction lists its locked inputs,
t0 / end quotes, returns, class and settlement reason; OQ-51). SYNTHETIC data."""

import json
from datetime import datetime, timedelta

import pytest

import sr
from sr.pipeline.orchestrator import RunContext
from sr.replay.report import prediction_report, to_markdown
from sr.replay.runner import replay_day
from tests.test_dataset import PEERS_ALL, REFS, FrameProvider, synthetic_quotes
from tests.test_forecast import DAY, NVDA, history, models
from tests.test_pipeline import Guarded


@pytest.fixture(scope="module")
def provider() -> FrameProvider:
    return FrameProvider(synthetic_quotes([NVDA, *PEERS_ALL, *REFS], seed=21))


@pytest.fixture
def replayed(conn, provider, tmp_path):  # type: ignore[no-untyped-def]
    m, h = models(conn, tmp_path), history()
    from sr.calendar import get_calendar

    s = get_calendar().session(DAY)
    assert s.open_at is not None
    first = provider.quotes_1s(list(provider.security_ids), s.open_at - timedelta(minutes=20), s.open_at)
    closes = {
        sid: float((g["bid"].iloc[0] + g["ask"].iloc[0]) / 2)
        for sid, g in first.sort_values("ts").groupby("security_id")
    }

    def ctx(t: datetime) -> RunContext:
        return RunContext(Guarded(provider, t), m, h, prev_close=closes, feature_dir=tmp_path)

    return replay_day(conn, NVDA, DAY, ctx, lambda t: Guarded(provider, t), out_dir=tmp_path)


def test_day_replay_runs_each_slot_and_settles(conn, replayed) -> None:  # type: ignore[no-untyped-def]
    assert len(replayed.pipeline_run_ids) == 6  # every sched-0.1 slot (AC-52)
    preds = conn.execute("select * from predictions order by published_at, target_row_id").fetchall()
    assert (
        len(preds) == 11
        and {p["sampling_rule"] for p in preds} == {"schedule_slot"}
        and all(p["is_primary"] for p in preds)
    )
    assert {p["schedule_slot_id"] for p in preds} == {
        "s0830_pre_open",
        "s1000",
        "s1130",
        "s1300",
        "s1430",
        "s1630_next",
    }
    modelled = [p for p in preds if p["target_row_id"] in ("tgt_regular_60m_v1", "tgt_regular_60m_move_v1")]
    published = [p for p in modelled if p["status"] != "abstained"]
    assert published and {p["status"] for p in published} <= {"settled", "unsettleable"}
    assert all(r.status in ("settled", "unsettleable") for r in replayed.settlements.values())


def test_every_report_passes_its_checks(replayed) -> None:  # type: ignore[no-untyped-def]
    assert len(replayed.reports) == 11
    for r in replayed.reports:
        fails = [c for c in r["checks"] if c["result"] == "FAIL"]
        assert not fails, (r["prediction"]["prediction_id"], fails)


def test_a_report_lists_what_acceptance_asks_for(conn, replayed) -> None:  # type: ignore[no-untyped-def]
    pid = next(
        r["prediction"]["prediction_id"]
        for r in replayed.reports
        if r["settlement"]
        and r["settlement"]["outcome_class"]
        and r["prediction"]["target_row_id"] == "tgt_regular_60m_v1"
    )
    r = prediction_report(conn, pid)
    md = to_markdown(r)
    assert (
        "锁定输入 locked" in md and "target_definition_version" in md and sr.SCHEMA_VERSION in md
    )  # locked inputs
    assert r["t0_quote"]["quote_id"] in md and r["end_quote"]["quote_id"] in md  # t0 / end quotes
    assert "相对" in md and "类别 outcome" in md and r["settlement"]["outcome_class"] in md  # returns + class
    assert r["settlement"]["reason_text"] in md  # settlement reason
    assert r["t0_quote"]["quote_ts"] > r["prediction"]["published_at"]
    assert r["end_quote"]["quote_ts"] >= r["prediction"]["target_end_at"]


def test_move_and_abstained_reports(conn, replayed) -> None:  # type: ignore[no-untyped-def]
    mv = next(
        r
        for r in replayed.reports
        if r["prediction"]["target_row_id"] == "tgt_regular_60m_move_v1" and r["settlement"]
    )
    md = to_markdown(mv)
    assert "|move|" in md and "pinball" in md and "预期波动 move" in md
    for r in replayed.reports:
        if r["prediction"]["status"] == "abstained":
            assert "弃预测，不结算" in to_markdown(r)


def test_files_written_and_html_is_inert(replayed) -> None:  # type: ignore[no-untyped-def]
    md = replayed.markdown_path.read_text()
    h = replayed.html_path.read_text()
    assert md.startswith("# 回放报告 replay report · sec_nvda · 2026-12-10") and md.count("\n## ") == 11
    assert "<script" not in h and "SYNTHETIC" in h and h.startswith("<!doctype html>")


def test_checks_catch_a_t0_before_publish(conn, replayed) -> None:  # type: ignore[no-untyped-def]
    """A forecast whose start quote is older than its publication must be flagged."""
    src = conn.execute("select * from predictions where status = 'settled' limit 1").fetchone()
    early = conn.execute(
        "select quote_id from reference_quotes where security_id = 'sec_nvda' and quote_ts < %s order by quote_ts limit 1",
        (src["published_at"],),
    ).fetchone()
    pid = "pred_bad_t0"
    cols = [
        "run_id",
        "target_row_id",
        "security_id",
        "display_tier",
        "is_primary",
        "sampling_rule",
        "valid_until",
        "published_at",
        "probabilities",
        "predicted_class",
        "sigma_hat_pp",
        "threshold_pp",
        "schedule_slot_id",
        "schedule_version",
        "scheduled_for",
    ]
    conn.execute(
        f"""insert into predictions (prediction_id, status, locked, t0_quote_id, {", ".join(cols)})
            select %s, 'awaiting_settlement', locked, %s, {", ".join(cols)} from predictions where prediction_id = %s""",
        (pid, early["quote_id"], src["prediction_id"]),
    )
    r = prediction_report(conn, pid)
    bad = next(c for c in r["checks"] if c["check"].startswith("published_at < t0"))
    assert bad["result"] == "FAIL"
    assert json.dumps(r, default=str)  # the report is serialisable for the web page (1.19)
