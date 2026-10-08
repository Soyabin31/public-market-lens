from __future__ import annotations

from marketlens.calendar.us import USMarketCalendar


def test_us_market_holidays_are_not_trading_sessions():
    calendar = USMarketCalendar()

    holidays = [
        "2026-01-01",  # New Year's Day
        "2026-01-19",  # Martin Luther King Jr. Day
        "2026-02-16",  # Presidents' Day
        "2026-04-03",  # Good Friday
        "2026-05-25",  # Memorial Day
        "2026-06-19",  # Juneteenth
        "2026-07-03",  # Independence Day - observed
        "2026-07-04",  # Independence Day - actual date, Saturday
        "2026-09-07",  # Labor Day
        "2026-11-26",  # Thanksgiving Day
        "2026-12-25",  # Christmas Day
    ]

    for holiday in holidays:
        assert not calendar.is_trading_session(holiday), holiday


def test_normal_us_market_session():
    calendar = USMarketCalendar()

    assert calendar.session_status("2026-09-15") == "NORMAL_SESSION"
    assert calendar.is_trading_session("2026-09-15")


def test_us_weekends_are_not_trading_sessions():
    calendar = USMarketCalendar()

    assert not calendar.is_trading_session("2026-09-19")  # Saturday
    assert not calendar.is_trading_session("2026-09-20")  # Sunday