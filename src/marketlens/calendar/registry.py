from __future__ import annotations

import pandas as pd

from marketlens.calendar.base import MarketCalendar
from marketlens.calendar.india_nse import IndiaNSECalendar
from marketlens.calendar.us import USMarketCalendar


def get_market_calendar(
        market: str,
        year: int | None = None,
) -> MarketCalendar:
    """
    Return the Market Lens calendar for a market.

    India:
        Official NSE calendar configuration.

    US:
        NYSE calendar provided by pandas-market-calendars.
    """

    normalized_market = market.strip().lower()

    if normalized_market == "india":
        if year is None:
            year = pd.Timestamp.today().year

        return IndiaNSECalendar(year)

    if normalized_market == "us":
        return USMarketCalendar()

    raise ValueError(
        f"Unsupported market calendar: {market}"
    )