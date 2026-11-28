"""DP 1.11 dataset build: splits, embargo, event clusters, exclusions (D-19, D-20, D-09; OQ-45). SYNTHETIC data."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from sr.calendar import get_calendar
from sr.labels.window import window_label
from sr.marketdata.quote_rules import evaluate_quotes
from sr.timeguard import LookaheadError
from sr.train import dataset as ds

CAL = get_calendar()
START, END = date(2026, 12, 1), date(2026, 12, 16)  # 12 sessions, after the basket's effective date
REFS = ["sec_qqq", "sec_spy", "sec_smh", "sec_vix"]
HALT_DAY, GAP_DAY = date(2026, 12, 8), date(2026, 12, 9)
PEERS_ALL = [
    "sec_" + t.lower()
    for t in ["AMD", "AVGO", "MU", "QCOM", "TXN", "INTC", "ADI", "MRVL", "AMAT", "LRCX", "KLAC"]
]


class FrameProvider:
    """In-memory synthetic 5-second quotes (NOT market data)."""

    source_id = "src_test_synthetic"
    synthetic = True

    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df
        self.security_ids = set(df["security_id"].unique())

    def quotes_1s(self, ids: list[str], start: datetime, end: datetime) -> pd.DataFrame:
        d = self.df
        return d[
            d["security_id"].isin(ids) & (d["ts"] >= pd.Timestamp(start)) & (d["ts"] <= pd.Timestamp(end))
        ].reset_index(drop=True)


def synthetic_quotes(securities: list[str], seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    for s in CAL.open_sessions(START, END):
        assert s.open_at is not None and s.close_at is not None
        ts = pd.date_range(s.open_at - timedelta(minutes=20), s.close_at, freq="5s", tz="UTC")
        common = rng.normal(0, 0.0004, len(ts)).cumsum()  # shared sector factor
        for sid in securities:
            own = rng.normal(0, 0.0006, len(ts)).cumsum()
            mid = 100 * np.exp(common + own)
            f = pd.DataFrame(
                {
                    "ts": ts,
                    "security_id": sid,
                    "quote_ts": ts,
                    "received_at": ts + pd.Timedelta(milliseconds=200),
                    "bid": mid - 0.005,
                    "ask": mid + 0.005,
                    "last": mid,
                    "halted": False,
                    "luld_pause": False,
                }
            )
            if s.session_date == HALT_DAY and sid == "sec_nvda":  # 3-minute halt 11:00 ET
                h = (f["ts"] >= pd.Timestamp(s.open_at + timedelta(minutes=90))) & (
                    f["ts"] < pd.Timestamp(s.open_at + timedelta(minutes=93))
                )
                f.loc[h, "halted"] = True
            if s.session_date == GAP_DAY and sid in (
                "sec_amd",
                "sec_mu",
            ):  # two constituents missing 10:00-10:10 ET
                f = f[
                    ~(
                        (f["ts"] >= pd.Timestamp(s.open_at + timedelta(minutes=30)))
                        & (f["ts"] < pd.Timestamp(s.open_at + timedelta(minutes=40)))
                    )
                ]
            frames.append(f)
    return pd.concat(frames, ignore_index=True)


@pytest.fixture(scope="module")
def provider() -> FrameProvider:
    peers = [
        "sec_" + t.lower()
        for t in ["AMD", "AVGO", "MU", "QCOM", "TXN", "INTC", "ADI", "MRVL", "AMAT", "LRCX", "KLAC"]
    ]
    return FrameProvider(synthetic_quotes(["sec_nvda", *peers, *REFS]))


# ---------------------------------------------------------------- splits and clusters (no DB)
def test_split_days_with_embargo() -> None:
    days = [s.session_date for s in CAL.open_sessions(START, END)]
    split_of, meta = ds.split_days(days)
    assert [m["name"] for m in meta] == ["train", "calibration", "validation", "holdout"]
    assert [m["embargo_days"] for m in meta] == [1, 1, 1, 0]
    counts = pd.Series(split_of).value_counts().to_dict()
    assert counts == {"train": 6, "embargo": 3, "calibration": 1, "validation": 1, "holdout": 1}
    # ordered in time, each boundary separated by exactly one embargo day
    seq = [split_of[d] for d in days]
    assert seq == ["train"] * 6 + ["embargo", "calibration", "embargo", "validation", "embargo", "holdout"]
    with pytest.raises(ValueError):
        ds.split_days(days[:6])


def test_clusters_merge_overlapping_events() -> None:
    d = [date(2026, 12, x) for x in (1, 2, 3, 4, 7, 8)]
    got = ds.clusters({"e1": {d[0], d[1], d[2]}, "e2": {d[2], d[3]}, "e3": {d[5]}})
    assert got[d[0]] == got[d[3]] == "evc:e1" and got[d[5]] == "evc:e3" and d[4] not in got


def test_minute_mids_are_labelled_by_minute_end() -> None:
    q = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                ["2026-12-01 15:19:05", "2026-12-01 15:19:55", "2026-12-01 15:20:01"], utc=True
            ),
            "security_id": "sec_nvda",
            "mid": [1.0, 2.0, 3.0],
        }
    )
    m = ds.minute_mids(q)["NVDA"]
    assert m.loc[pd.Timestamp("2026-12-01 15:20", tz="UTC")] == 2.0  # 15:19 bar is visible from 15:20:00
    assert pd.Timestamp("2026-12-01 15:19", tz="UTC") not in m.index


def test_window_label_refuses_unfinished_window(provider: FrameProvider) -> None:
    s = CAL.session(START)
    assert s.open_at is not None
    q = evaluate_quotes(
        provider.quotes_1s(["sec_nvda", "sec_amd", "sec_mu"], s.open_at - timedelta(minutes=20), s.close_at)
    )
    t = s.open_at + timedelta(minutes=30)
    w = {"sec_amd": 0.5, "sec_mu": 0.5}
    assert window_label(q, "sec_nvda", w, t, t + timedelta(hours=2)).status == "ok"
    with pytest.raises(LookaheadError):  # the 60-minute window has not ended by as_of
        window_label(q, "sec_nvda", w, t, t + timedelta(minutes=30))


# ---------------------------------------------------------------- end to end (DB)
PEERS = [
    "sec_" + t.lower()
    for t in ["AMD", "AVGO", "MU", "QCOM", "TXN", "INTC", "ADI", "MRVL", "AMAT", "LRCX", "KLAC"]
]
DAYS = [s.session_date for s in CAL.open_sessions(START, END)]
# an event covering the last train day + the first embargo day spans a boundary; one day-precision item
EVENTS = ({"evt_x": {DAYS[4], DAYS[5], DAYS[6]}}, {DAYS[2]})


@pytest.fixture(scope="module")
def rows(provider: FrameProvider) -> pd.DataFrame:
    mp = pytest.MonkeyPatch()
    try:  # same weights as the seeded bmv_semis_peer_ex_nvda_v1 (equal weight over 11 peers)
        mp.setattr(
            ds,
            "benchmark_version",
            lambda conn, sec, d: ("bmv_semis_peer_ex_nvda_v1", {p: 1 / 11 for p in PEERS}),
        )
        mp.setattr(ds, "_event_sessions", lambda *a: EVENTS)
        return ds.build_rows(None, provider, ["sec_nvda"], START, END)
    finally:
        mp.undo()


@pytest.fixture
def built(conn, provider, rows, tmp_path):  # type: ignore[no-untyped-def]
    return ds.build_dataset(conn, provider, ["sec_nvda"], START, END, out_dir=tmp_path, rows=rows)


def test_dataset_row_and_exclusions(conn, built) -> None:  # type: ignore[no-untyped-def]
    r, f = built.row, built.frame
    assert r["dataset_version_id"].startswith("ds_") and r["target_id"] == "regular_60m"
    assert r["feature_set_version"] == "fs-0.2" and r["label_version"] == "lbl-0.1"
    assert r["time_range"] == {"start": "2026-12-01", "end": "2026-12-16"}
    assert len(f) == 12 * 78  # every 5-minute grid time is a candidate row
    ex = r["exclusions"]
    assert ex["window_insufficient"] == 11 * 12  # 15:00-15:55 ET: t0 + 60m + 30s > close (D-18)
    assert ex["news_time_unknown"] == 78  # the whole day with a day-precision item (its own reason wins)
    assert ex["insufficient_data"] > 0  # sigma needs >= 10 windows from earlier sessions (days 1-2)
    assert ex["crosses_split_boundary"] > 0 and ex["halted"] > 0 and ex["no_sync_start_quote"] > 0
    assert ex["news_time_unknown"] > 0
    kept = f[f["exclusion"].isna()]
    assert r["n_rows"] == len(kept) > 0 and r["n_trading_days"] == kept["session_date"].nunique()
    assert sum(r["class_balance"].values()) == pytest.approx(1.0, abs=1e-5)
    assert r["availability_check_passed"] is True
    stored = conn.execute(
        "select * from training_dataset_versions where dataset_version_id = %s", (r["dataset_version_id"],)
    ).fetchone()
    assert stored["n_rows"] == r["n_rows"] and stored["splits"] == r["splits"] and stored["exclusions"] == ex


def test_no_kept_row_crosses_a_boundary(built) -> None:  # type: ignore[no-untyped-def]
    f = built.frame
    kept = f[f["exclusion"].isna()]
    assert "embargo" not in set(kept["split"])
    days = [s.session_date for s in CAL.open_sessions(START, END)]
    # the cluster starts in train (days 4-5), so its rows on later days are out
    assert set(kept.loc[kept["event_cluster"] == "evc:evt_x", "split"]) == {"train"}
    assert not ((f["session_date"] == days[6]) & f["exclusion"].isna()).any()
    assert built.row["n_event_clusters"] == 1
    # every split's kept rows lie inside that split's dates
    for m in built.row["splits"]:
        k = kept[kept["split"] == m["name"]]
        assert k.empty or (
            k["session_date"].min().isoformat() >= m["start"]
            and k["session_date"].max().isoformat() <= m["end"]
        )


def test_sigma_uses_earlier_sessions_only(built) -> None:  # type: ignore[no-untyped-def]
    f = built.frame
    days = [s.session_date for s in CAL.open_sessions(START, END)]
    first_two = f[f["session_date"].isin(days[:2]) & f["relative_return_pp"].notna()]
    assert (first_two["exclusion"] == "insufficient_data").all()  # < 10 same-bucket windows before day 3
    labelled = f[f["label"].notna()]
    assert labelled["session_date"].min() == days[3] or labelled["session_date"].min() == days[2]
    k = f[f["exclusion"].isna()]
    assert ((k["threshold_pp"] - 0.25 * k["sigma_hat_pp"]).abs() < 1e-9).all()  # D-09 k = 0.25


def test_features_present_and_point_in_time(built) -> None:  # type: ignore[no-untyped-def]
    k = built.frame[built.frame["exclusion"].isna()]
    for c in (
        "f_minutes_since_open",
        "f_qqq_ret_30m",
        "f_amd_ret_5m",
        "f_smh_ret_15m",
        "f_rv_30m",
        "f_vix_level",
    ):
        assert c in k.columns and k[c].notna().any(), c
    assert (k["t0_quote_ts"] > k["sample_ts"]).all()


def test_manifest_written(built, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    d = tmp_path / built.dataset_version_id
    assert (d / "rows.parquet").exists() and (d / "manifest.json").exists()
    back = pd.read_parquet(d / "rows.parquet")
    assert len(back) == len(built.frame)


def test_rebuild_is_deterministic(conn, provider, rows, tmp_path, built) -> None:  # type: ignore[no-untyped-def]
    short_end = DAYS[3]
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(
            ds,
            "benchmark_version",
            lambda conn, sec, d: ("bmv_semis_peer_ex_nvda_v1", {p: 1 / 11 for p in PEERS}),
        )
        mp.setattr(ds, "_event_sessions", lambda *a: EVENTS)
        again = ds.build_rows(None, provider, ["sec_nvda"], START, short_end)
    finally:
        mp.undo()
    cols = ["sample_ts", "exclusion", "label", "relative_return_pp"]
    first = rows[rows["session_date"] <= short_end][cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(first, again[cols].reset_index(drop=True))
    child = ds.build_dataset(
        conn,
        provider,
        ["sec_nvda"],
        START,
        END,
        out_dir=tmp_path,
        rows=rows,
        parent_dataset_version_id=built.dataset_version_id,
    )
    assert child.row["parent_dataset_version_id"] == built.dataset_version_id
    assert child.dataset_version_id != built.dataset_version_id  # a new version, never an update


def test_move_target_needs_no_sigma(provider) -> None:  # type: ignore[no-untyped-def]
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(ds, "benchmark_version", lambda conn, sec, d: ("bmv_x", {p: 1 / 11 for p in PEERS}))
        mp.setattr(ds, "_event_sessions", lambda *a: ({}, set()))
        f = ds.build_rows(None, provider, ["sec_nvda"], START, DAYS[2], target_id="regular_60m_move")
    finally:
        mp.undo()
    assert "insufficient_data" not in set(f["exclusion"].dropna())
    k = f[f["exclusion"].isna()]
    assert len(k) > 0 and (k["label_value"] >= 0).all() and "label" not in k.columns


def test_build_before_last_close_is_refused(conn, provider) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError):
        ds.build_rows(
            conn, provider, ["sec_nvda"], START, END, as_of=datetime(2026, 12, 16, 18, 0, tzinfo=UTC)
        )


def test_event_sessions_from_db(conn, doc_storage) -> None:  # type: ignore[no-untyped-def]
    """An event with precise evidence on 2026-12-02 covers 12-02 .. +2 sessions (OQ-45)."""
    from sr.events.merge import EvidenceIn, attach_evidence
    from sr.evidence.collection_log import run_collection
    from tests.test_collection_reasoning import ASOF, WINDOW, scenario

    sources, _ = scenario(conn)
    res = run_collection(conn, "sec_nvda", sources, WINDOW, ASOF, storage=doc_storage, now=ASOF)
    item = conn.execute(
        "select * from collection_items where collection_run_id = %s and disposition = 'kept' and channel = 'news_wire' limit 1",
        (res.collection_run_id,),
    ).fetchone()
    m = attach_evidence(
        conn,
        "policy:BIS:x",
        "policy_export",
        EvidenceIn(item["doc_version_id"], "c", {}, "primary_confirmed", "o"),
        now=ASOF,
    )
    conn.execute(
        "insert into event_security_links (event_id, security_id, relation) values (%s, 'sec_nvda', 'regulated_party')",
        (m.event_id,),
    )
    sessions = CAL.open_sessions(date(2026, 12, 1), date(2026, 12, 9))
    cover, unknown = ds._event_sessions(conn, "sec_nvda", datetime(2026, 12, 10, tzinfo=UTC), sessions)
    assert cover[m.event_id] == {date(2026, 12, 2), date(2026, 12, 3), date(2026, 12, 4)} and unknown == set()
    # evidence not yet available at the build time is not used (point in time)
    assert ds._event_sessions(conn, "sec_nvda", datetime(2026, 12, 2, 15, 0, tzinfo=UTC), sessions)[0] == {}


def test_move_dataset_row(conn, provider, rows, tmp_path) -> None:  # type: ignore[no-untyped-def]
    mv = rows.drop(columns=["label", "sigma_hat_pp", "threshold_pp"])
    mv.loc[mv["exclusion"] == "insufficient_data", "exclusion"] = None  # the move target needs no sigma
    mv["label_value"] = mv["relative_return_pp"].abs()
    r = ds.build_dataset(
        conn, provider, ["sec_nvda"], START, END, target_id="regular_60m_move", out_dir=tmp_path, rows=mv
    )
    b = r.row["class_balance"]
    assert set(b) == {"p50", "p80", "p90"} and 0 <= b["p50"] <= b["p80"] <= b["p90"]
    assert r.row["target_id"] == "regular_60m_move" and "insufficient_data" not in r.row["exclusions"]
