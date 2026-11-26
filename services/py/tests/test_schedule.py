"""AC-52 (P0 part): schedule_slots(date) for sched-0.1."""

from datetime import UTC, date, datetime

from sr.calendar import schedule_slots
from tests.conftest import et


def test_normal_day_six_slots_utc() -> None:
    slots = schedule_slots(date(2026, 12, 1))
    assert [s.slot_id for s in slots] == ["s0830_pre_open", "s1000", "s1130", "s1300", "s1430", "s1630_next"]
    assert all(s.status == "scheduled" for s in slots)
    assert [s.scheduled_for.strftime("%H:%M") for s in slots] == [
        "13:30",
        "15:00",
        "16:30",
        "18:00",
        "19:30",
        "21:30",
    ]
    assert all(s.scheduled_for.tzinfo == UTC for s in slots)
    by = {s.slot_id: s for s in slots}
    assert by["s1430"].target_ids == ("regular_60m", "regular_60m_move", "regular_to_close")
    assert by["s1000"].target_ids == ("regular_60m", "regular_60m_move")
    assert by["s0830_pre_open"].target_ids == ("next_regular_session",)
    assert all(s.schedule_version == "sched-0.1" for s in slots)
    # 4 regular_60m forecasts per normal day (AC-52)
    assert sum("regular_60m" in s.target_ids for s in slots) == 4


def test_half_day_expansion() -> None:
    slots = {s.slot_id: s for s in schedule_slots(date(2026, 11, 27))}
    sched = [k for k, s in slots.items() if s.status == "scheduled"]
    assert sched == ["s0830_pre_open", "s1000", "s1130", "s1630_next"]
    assert slots["s1300"].status == "not_scheduled" and slots["s1430"].status == "not_scheduled"
    assert "regular_to_close" in slots["s1130"].target_ids
    assert "regular_to_close" not in slots["s1430"].target_ids
    assert slots["s1630_next"].time_et == "13:30"
    assert slots["s1630_next"].scheduled_for == datetime(2026, 11, 27, 18, 30, tzinfo=UTC)


def test_holiday_returns_empty() -> None:
    assert schedule_slots(date(2026, 11, 26)) == []
    assert schedule_slots(date(2026, 11, 28)) == []  # Saturday


def test_dst_changes_utc_of_1000_et() -> None:
    before = {s.slot_id: s for s in schedule_slots(date(2026, 10, 30))}["s1000"].scheduled_for
    after = {s.slot_id: s for s in schedule_slots(date(2026, 11, 2))}["s1000"].scheduled_for
    assert before.hour == 14 and after.hour == 15
    assert before == et(date(2026, 10, 30), "10:00") and after == et(date(2026, 11, 2), "10:00")
