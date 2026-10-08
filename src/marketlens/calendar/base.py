from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class MarketCalendar(ABC):
    """
    Market Lens abstraction for exchange trading calendars.

    Downstream components such as breadth, feature engineering,
    backtesting and prediction must depend on this interface,
    not directly on a third-party calendar library.
    """

    @property
    @abstractmethod
    def market(self) -> str:
        """Return the Market Lens market identifier."""
        raise NotImplementedError

    @property
    @abstractmethod
    def exchange(self) -> str:
        """Return the exchange identifier."""
        raise NotImplementedError

    @property
    @abstractmethod
    def timezone(self) -> str:
        """Return the exchange timezone."""
        raise NotImplementedError

    @abstractmethod
    def session_status(self, session_date: date | str) -> str:
        """
        Return the session status for a date.

        Possible values:

        NORMAL_SESSION
        HOLIDAY
        SPECIAL_SESSION
        """
        raise NotImplementedError

    def is_trading_session(
            self,
            session_date: date | str,
    ) -> bool:
        """
        Return True when the exchange has a trading session
        on the supplied date.
        """
        status = self.session_status(session_date)

        return status in {
            "NORMAL_SESSION",
            "SPECIAL_SESSION",
        }

    @abstractmethod
    def sessions(
            self,
            start_date: date | str,
            end_date: date | str,
    ) -> pd.DatetimeIndex:
        """
        Return all trading-session dates in the requested range.
        """
        raise NotImplementedError

    def filter_sessions(
            self,
            df: pd.DataFrame,
            date_column: str = "date",
    ) -> pd.DataFrame:
        """
        Keep only rows belonging to valid trading sessions.
        """
        if date_column not in df.columns:
            raise ValueError(
                f"Missing required date column: {date_column}"
            )

        if df.empty:
            return df.copy()

        result = df.copy()

        result[date_column] = (
            pd.to_datetime(result[date_column])
            .dt.normalize()
        )

        start_date = result[date_column].min()
        end_date = result[date_column].max()

        valid_sessions = self.sessions(
            start_date=start_date,
            end_date=end_date,
        )

        return result[
            result[date_column].isin(valid_sessions)
        ].copy()