from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from collections.abc import Sequence
from typing import Any

from marketlens.intraday.models import IntradayCandle


@dataclass(frozen=True)
class MarketSessionHours:
    """
    Authoritative regular trading session hours and square-off rules.
    """

    market: str
    open_time: time
    close_time: time
    squareoff_cutoff_time: time
    timezone: str

    @property
    def total_session_minutes(self) -> int:
        open_minutes = self.open_time.hour * 60 + self.open_time.minute
        close_minutes = self.close_time.hour * 60 + self.close_time.minute
        return max(0, close_minutes - open_minutes)

    @property
    def tradeable_minutes_until_squareoff(self) -> int:
        open_minutes = self.open_time.hour * 60 + self.open_time.minute
        cutoff_minutes = self.squareoff_cutoff_time.hour * 60 + self.squareoff_cutoff_time.minute
        return max(0, cutoff_minutes - open_minutes)


NSE_SESSION = MarketSessionHours(
    market="india",
    open_time=time(9, 15),
    close_time=time(15, 30),
    squareoff_cutoff_time=time(15, 15),
    timezone="Asia/Kolkata",
)

US_SESSION = MarketSessionHours(
    market="us",
    open_time=time(9, 30),
    close_time=time(16, 0),
    squareoff_cutoff_time=time(15, 45),
    timezone="America/New_York",
)

MARKET_SESSIONS: dict[str, MarketSessionHours] = {
    "india": NSE_SESSION,
    "nse": NSE_SESSION,
    "us": US_SESSION,
    "nyse": US_SESSION,
    "nasdaq": US_SESSION,
}


def get_session_hours(market: str) -> MarketSessionHours:
    """Return the authoritative session hours for a market."""
    normalized = market.strip().lower()
    if normalized not in MARKET_SESSIONS:
        raise ValueError(f"Unsupported market for session hours: {market}")
    return MARKET_SESSIONS[normalized]


def calculate_bars_remaining(
    timestamp: datetime | Any,
    timeframe_minutes: int = 5,
    market: str = "india",
) -> int:
    """
    Calculate the number of complete bars remaining until the broker auto-square-off cutoff.

    If timestamp is not a datetime (e.g. integer index in synthetic tests),
    returns a high default (999) to prevent false disqualification.
    """
    if not isinstance(timestamp, datetime):
        return 999

    if timeframe_minutes <= 0:
        raise ValueError("timeframe_minutes must be greater than zero")

    session = get_session_hours(market)
    t = timestamp.time()

    current_minutes = t.hour * 60 + t.minute
    cutoff_minutes = session.squareoff_cutoff_time.hour * 60 + session.squareoff_cutoff_time.minute

    if current_minutes >= cutoff_minutes:
        return 0

    open_minutes = session.open_time.hour * 60 + session.open_time.minute
    if current_minutes < open_minutes:
        return session.tradeable_minutes_until_squareoff // timeframe_minutes

    remaining_minutes = cutoff_minutes - current_minutes
    return remaining_minutes // timeframe_minutes


def has_sufficient_session_time(
    timestamp: datetime | Any,
    min_bars: int = 6,
    timeframe_minutes: int = 5,
    market: str = "india",
) -> bool:
    """
    Check if at least min_bars remain before the broker auto-square-off cutoff.
    """
    remaining = calculate_bars_remaining(
        timestamp=timestamp,
        timeframe_minutes=timeframe_minutes,
        market=market,
    )
    return remaining >= min_bars


def find_session_end_index(
    candles: Sequence[IntradayCandle],
    start_index: int,
) -> int:
    """
    Find the index of the last candle belonging to the same trading day as candles[start_index].

    If timestamps are ints/non-datetimes, returns len(candles) - 1.
    """
    if not candles:
        raise ValueError("candles cannot be empty")

    if start_index < 0 or start_index >= len(candles):
        raise IndexError("start_index must reference an existing candle")

    ref_timestamp = candles[start_index].timestamp
    if not isinstance(ref_timestamp, datetime):
        return len(candles) - 1

    ref_date = ref_timestamp.date()
    last_idx = start_index

    for idx in range(start_index, len(candles)):
        c_ts = candles[idx].timestamp
        if isinstance(c_ts, datetime) and c_ts.date() == ref_date:
            last_idx = idx
        else:
            break

    return last_idx
