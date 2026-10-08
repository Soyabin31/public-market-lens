from __future__ import annotations

from datetime import date

import pandas as pd
import pandas_market_calendars as mcal

from marketlens.calendar.base import MarketCalendar


class USMarketCalendar(MarketCalendar):
    """
    US equity-market calendar backed by pandas-market-calendars.

    NYSE is used as the common equity-session calendar for the
    initial US Market Lens universe.

    This covers the current development universe of:
        - NYSE-listed stocks
        - Nasdaq-listed stocks
        - S&P 500 benchmark
        - Dow benchmark

    Exchange-specific differences can be introduced later if
    Market Lens starts using instruments requiring a different
    calendar.
    """

    def __init__(self) -> None:
        self._calendar = mcal.get_calendar("NYSE")

    @property
    def market(self) -> str:
        return "us"

    @property
    def exchange(self) -> str:
        return "NYSE"

    @property
    def timezone(self) -> str:
        return "America/New_York"

    def session_status(
            self,
            session_date: date | str,
    ) -> str:
        timestamp = pd.Timestamp(session_date).normalize()

        schedule = self._calendar.schedule(
            start_date=timestamp.date(),
            end_date=timestamp.date(),
        )

        if schedule.empty:
            return "HOLIDAY"

        return "NORMAL_SESSION"

    def sessions(
            self,
            start_date: date | str,
            end_date: date | str,
    ) -> pd.DatetimeIndex:
        start = pd.Timestamp(start_date).normalize()
        end = pd.Timestamp(end_date).normalize()

        if end < start:
            return pd.DatetimeIndex([])

        schedule = self._calendar.schedule(
            start_date=start.date(),
            end_date=end.date(),
        )

        return pd.DatetimeIndex(
            schedule.index
        ).normalize()