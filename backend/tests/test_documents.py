"""Regression test for the documents.py `_next_crawl_at` NameError bug:
the function was referenced by update_drive_sync_schedule and
execute_scheduled_drive_syncs but never defined anywhere, so both raised
NameError at call time. This exercises the real implementation directly."""
from datetime import datetime, timezone

from app.routers.documents import _next_crawl_at


def test_off_and_unrecognized_schedules_return_none():
    assert _next_crawl_at("off") is None
    assert _next_crawl_at(None) is None
    assert _next_crawl_at("bogus") is None


def test_daily_advances_one_day():
    now = datetime(2026, 3, 10, 8, 0, 0, tzinfo=timezone.utc)
    result = _next_crawl_at("daily", now)
    assert result == datetime(2026, 3, 11, 8, 0, 0, tzinfo=timezone.utc).isoformat()


def test_weekly_advances_seven_days():
    now = datetime(2026, 3, 10, 8, 0, 0, tzinfo=timezone.utc)
    result = _next_crawl_at("weekly", now)
    assert result == datetime(2026, 3, 17, 8, 0, 0, tzinfo=timezone.utc).isoformat()


def test_monthly_advances_one_calendar_month():
    now = datetime(2026, 3, 10, 8, 0, 0, tzinfo=timezone.utc)
    result = _next_crawl_at("monthly", now)
    assert result == datetime(2026, 4, 10, 8, 0, 0, tzinfo=timezone.utc).isoformat()


def test_monthly_rolls_over_december_to_january():
    now = datetime(2026, 12, 15, 8, 0, 0, tzinfo=timezone.utc)
    result = _next_crawl_at("monthly", now)
    assert result == datetime(2027, 1, 15, 8, 0, 0, tzinfo=timezone.utc).isoformat()


def test_monthly_clamps_day_to_target_month_length():
    # Jan 31 + 1 month -> Feb 28 (2027 is not a leap year), not an
    # out-of-range date error.
    now = datetime(2027, 1, 31, 8, 0, 0, tzinfo=timezone.utc)
    result = _next_crawl_at("monthly", now)
    assert result == datetime(2027, 2, 28, 8, 0, 0, tzinfo=timezone.utc).isoformat()


def test_monthly_clamps_to_leap_day_in_leap_year():
    now = datetime(2028, 1, 31, 8, 0, 0, tzinfo=timezone.utc)
    result = _next_crawl_at("monthly", now)
    assert result == datetime(2028, 2, 29, 8, 0, 0, tzinfo=timezone.utc).isoformat()


def test_defaults_to_now_when_no_base_given():
    # Just verify it doesn't raise and returns a parseable ISO string in the
    # future relative to a moment we captured just before calling it.
    before = datetime.now(timezone.utc)
    result = _next_crawl_at("daily")
    assert result is not None
    parsed = datetime.fromisoformat(result)
    assert parsed > before
