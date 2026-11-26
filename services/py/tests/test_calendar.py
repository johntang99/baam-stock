"""AC-02 (sessions, half days, DST) and AC-03 (window availability)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from sr.calendar import is_target_available, next_regular_session, session
from sr.timeguard import NaiveDatetimeError
from tests.conftest import et

D_NORMAL = date(2026, 12, 1)  # Tuesday
D_THANKSGIVING = date(2026, 11, 26)
D_HALF = date(2026, 11, 27)
D_XMAS_EVE = date(2026, 12, 24)


# ---------------- AC-02 ----------------
def test_thanksgiving_closed() -> None:
    s = session(D_THANKSGIVING)
    assert s.status == "closed" and s.open_at is None and s.close_at is None


@pytest.mark.parametrize("d", [D_HALF, D_XMAS_EVE])
def test_half_days_close_1300_et(d: date) -> None:
    s = session(d)
    assert s.status == "early_close"
    assert s.open_at == datetime(d.year, d.month, d.day, 14, 30, tzinfo=UTC)  # 09:30 EST
    assert s.close_at == datetime(d.year, d.month, d.day, 18, 0, tzinfo=UTC)  # 13:00 EST
    assert s.close_at.astimezone(et(d, "00:00").tzinfo).strftime("%H:%M") == "13:00"  # type: ignore[union-attr]


def test_normal_day_utc() -> None:
    s = session(D_NORMAL)
    assert s.status == "open"
    assert s.open_at == datetime(2026, 12, 1, 14, 30, tzinfo=UTC)
    assert s.close_at == datetime(2026, 12, 1, 21, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "before,after",
    [
        (date(2026, 10, 30), date(2026, 11, 2)),  # DST ends 2026-11-01
        (date(2027, 3, 12), date(2027, 3, 15)),
    ],  # DST starts 2027-03-14
)
def test_dst_switch_utc_offsets(before: date, after: date) -> None:
    b, a = session(before), session(after)
    assert b.open_at and a.open_at
    assert (b.open_at.hour, a.open_at.hour) in {(13, 14), (14, 13)}
    # wall clock stays 09:30 ET on both sides
    assert et(before, "09:30") == b.open_at and et(after, "09:30") == a.open_at


def test_weekend_closed() -> None:
    assert session(date(2026, 11, 28)).status == "closed"


def test_session_rejects_datetime() -> None:
    with pytest.raises(TypeError):
        session(datetime(2026, 12, 1, tzinfo=UTC))  # type: ignore[arg-type]


# ---------------- AC-03 ----------------
def test_60m_available_at_1459_00() -> None:
    a = is_target_available("regular_60m", et(D_NORMAL, "14:59:00"))
    assert a.available and a.abstain_reason is None


def test_60m_unavailable_at_1459_45() -> None:
    a = is_target_available("regular_60m", et(D_NORMAL, "14:59:45"))
    assert not a.available and a.abstain_reason == "window_insufficient"


def test_60m_boundary_exactly_1459_30() -> None:
    assert is_target_available("regular_60m", et(D_NORMAL, "14:59:30")).available  # t0+60m+30s == close
    assert not is_target_available(
        "regular_60m", et(D_NORMAL, "14:59:30") + timedelta(milliseconds=1)
    ).available


def test_move_target_follows_60m_rule() -> None:
    assert is_target_available("regular_60m_move", et(D_NORMAL, "14:59:00")).available
    assert not is_target_available("regular_60m_move", et(D_NORMAL, "14:59:45")).available


def test_to_close_1544_available_1546_not() -> None:
    a = is_target_available("regular_to_close", et(D_NORMAL, "15:44"))
    assert a.available and a.window_end_at == datetime(2026, 12, 1, 21, 0, tzinfo=UTC)
    b = is_target_available("regular_to_close", et(D_NORMAL, "15:46"))
    assert not b.available and b.abstain_reason == "window_insufficient"
    assert is_target_available(
        "regular_to_close", et(D_NORMAL, "15:45")
    ).available  # 15 min inclusive (OQ-11)


def test_half_day_1230_60m_unavailable() -> None:
    a = is_target_available("regular_60m", et(D_HALF, "12:30"))
    assert not a.available and a.abstain_reason == "window_insufficient"
    assert is_target_available("regular_to_close", et(D_HALF, "12:30")).available


@pytest.mark.parametrize("ts", ["08:30", "16:30", "09:29:59"])
def test_60m_outside_regular_session_is_market_closed(ts: str) -> None:
    a = is_target_available("regular_60m", et(D_NORMAL, ts))
    assert not a.available and a.abstain_reason == "market_closed"


def test_60m_on_holiday_market_closed() -> None:
    a = is_target_available("regular_60m", et(D_THANKSGIVING, "11:00"))
    assert not a.available and a.abstain_reason == "market_closed"


def test_saturday_next_session_is_monday() -> None:
    sat = et(date(2026, 11, 28), "12:00")
    s = next_regular_session(sat)
    assert s.session_date == date(2026, 11, 30)
    a = is_target_available("next_regular_session", sat)
    assert a.available and a.session and a.session.session_date == date(2026, 11, 30)


def test_next_session_from_preopen_is_same_day_and_from_1630_is_next_day() -> None:
    assert next_regular_session(et(D_NORMAL, "08:30")).session_date == D_NORMAL
    assert next_regular_session(et(D_NORMAL, "16:30")).session_date == date(2026, 12, 2)
    # Wednesday 16:30 before Thanksgiving -> Friday half day
    assert next_regular_session(et(date(2026, 11, 25), "16:30")).session_date == D_HALF


def test_naive_datetime_rejected() -> None:
    with pytest.raises(NaiveDatetimeError):
        is_target_available("regular_60m", datetime(2026, 12, 1, 15, 0))  # noqa: DTZ001 (deliberately naive)
    with pytest.raises(ValueError):
        is_target_available("overnight_gap", et(D_NORMAL, "10:00"))


def test_availability_is_utc_consistent() -> None:
    # same instant expressed in UTC gives the same answer
    t = et(D_NORMAL, "14:59:00").astimezone(UTC)
    assert is_target_available("regular_60m", t).available
    assert (
        is_target_available("regular_60m", t + timedelta(seconds=45)).abstain_reason == "window_insufficient"
    )
