from __future__ import annotations

import pandas as pd

from marketlens.calendar import get_market_calendar


def test_known_2026_nse_holidays_are_not_trading_sessions() -> None:
    calendar = get_market_calendar(
        "india",
        year=2026,
    )

    holidays = [
        "2026-01-15",
        "2026-01-26",
        "2026-02-19",
        "2026-03-03",
        "2026-03-19",
        "2026-03-26",
        "2026-03-31",
        "2026-04-01",
        "2026-04-03",
        "2026-04-14",
        "2026-05-01",
        "2026-05-28",
        "2026-06-26",
        "2026-08-26",
        "2026-09-14",
        "2026-10-02",
        "2026-10-20",
        "2026-11-10",
        "2026-11-24",
        "2026-12-25",
    ]

    for holiday in holidays:
        assert not calendar.is_trading_session(holiday), (
            f"{holiday} should be an NSE holiday"
        )


def test_normal_nse_session_is_trading_session() -> None:
    calendar = get_market_calendar(
        "india",
        year=2026,
    )

    assert calendar.is_trading_session(
        "2026-09-15"
    )


def test_weekends_are_not_normal_trading_sessions() -> None:
    calendar = get_market_calendar(
        "india",
        year=2026,
    )

    assert not calendar.is_trading_session(
        "2026-09-19"
    )

    assert not calendar.is_trading_session(
        "2026-09-20"
    )


def test_muhurat_trading_is_special_session() -> None:
    calendar = get_market_calendar(
        "india",
        year=2026,
    )

    assert (
            calendar.session_status("2026-11-08")
            == "SPECIAL_SESSION"
    )

    assert calendar.is_trading_session(
        "2026-11-08"
    )


def test_sessions_exclude_holidays() -> None:
    calendar = get_market_calendar(
        "india",
        year=2026,
    )

    sessions = calendar.sessions(
        "2026-09-11",
        "2026-09-15",
    )

    assert pd.Timestamp("2026-09-11") in sessions

    assert pd.Timestamp("2026-09-12") not in sessions
    assert pd.Timestamp("2026-09-13") not in sessions
    assert pd.Timestamp("2026-09-14") not in sessions

    assert pd.Timestamp("2026-09-15") in sessions