from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from marketlens.calendar.base import MarketCalendar


PROJECT_ROOT = Path(__file__).resolve().parents[3]

CALENDAR_DIRECTORY = (
        PROJECT_ROOT / "config" / "calendars"
)


class IndiaNSECalendar(MarketCalendar):
    """
    NSE Capital Market calendar.

    The official NSE calendar configuration is the
    authoritative source for exchange-specific holidays
    and special sessions.

    Weekends are handled programmatically.
    """

    def __init__(
            self,
            year: int,
    ) -> None:
        self.year = year

        path = (
                CALENDAR_DIRECTORY
                / f"india_nse_{year}.yaml"
        )

        if not path.exists():
            raise FileNotFoundError(
                f"NSE calendar configuration not found: {path}"
            )

        with path.open(
                "r",
                encoding="utf-8",
        ) as file:
            self.config = yaml.safe_load(file)

        self._validate_config()

    @property
    def market(self) -> str:
        return self.config["market"]

    @property
    def exchange(self) -> str:
        return self.config["exchange"]

    @property
    def timezone(self) -> str:
        return self.config["timezone"]

    def _validate_config(self) -> None:
        required = {
            "market",
            "exchange",
            "timezone",
            "calendar_year",
            "weekend_days",
            "sessions",
        }

        missing = required - set(self.config)

        if missing:
            raise ValueError(
                "Invalid NSE calendar configuration. "
                f"Missing fields: {sorted(missing)}"
            )

        if self.config["calendar_year"] != self.year:
            raise ValueError(
                f"Calendar year mismatch: "
                f"requested={self.year}, "
                f"configured={self.config['calendar_year']}"
            )

    def _status_for_date(
            self,
            session_date: date | str,
    ) -> str | None:
        timestamp = pd.Timestamp(session_date).normalize()
        date_key = timestamp.strftime("%Y-%m-%d")

        session_config = self.config["sessions"].get(
            date_key
        )

        if session_config is None:
            return None

        return session_config["status"]

    def session_status(
            self,
            session_date: date | str,
    ) -> str:
        timestamp = pd.Timestamp(session_date).normalize()

        # Explicit exchange configuration always wins.
        explicit_status = self._status_for_date(
            timestamp
        )

        if explicit_status is not None:
            return explicit_status

        # Saturday / Sunday are normally closed.
        if timestamp.dayofweek >= 5:
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

        dates = pd.date_range(
            start=start,
            end=end,
            freq="D",
        )

        valid_dates = [
            current_date
            for current_date in dates
            if self.is_trading_session(current_date)
        ]

        return pd.DatetimeIndex(valid_dates)