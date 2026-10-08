from __future__ import annotations

import numpy as np
import pandas as pd


def percentage_return(series: pd.Series, periods: int = 1) -> pd.Series:
    """
    Calculate percentage return over the specified number of periods.

    Example:
        periods=1  -> 1-day return
        periods=5  -> 5-day return
    """
    return series.pct_change(periods=periods)


def moving_average(
        series: pd.Series,
        window: int,
) -> pd.Series:
    """
    Calculate a simple moving average.
    """
    if window <= 0:
        raise ValueError("window must be greater than zero")

    return series.rolling(window=window).mean()


def distance_from_moving_average(
        series: pd.Series,
        window: int,
) -> pd.Series:
    """
    Calculate percentage distance of price from its moving average.

    Formula:
        (price / moving_average) - 1
    """
    ma = moving_average(series, window)

    return (series / ma) - 1.0


def rate_of_change(
        series: pd.Series,
        periods: int = 20,
) -> pd.Series:
    """
    Calculate rate of change over the specified number of periods.
    """
    if periods <= 0:
        raise ValueError("periods must be greater than zero")

    return (series / series.shift(periods)) - 1.0


def realised_volatility(
        returns: pd.Series,
        window: int = 20,
        annualisation_factor: int = 252,
) -> pd.Series:
    """
    Calculate annualised rolling realised volatility.

    The input is expected to be periodic returns.
    """
    if window <= 0:
        raise ValueError("window must be greater than zero")

    return (
            returns
            .rolling(window=window)
            .std()
            * np.sqrt(annualisation_factor)
    )


def rsi(
        series: pd.Series,
        window: int = 14,
) -> pd.Series:
    """
    Calculate the Relative Strength Index (RSI).

    Uses the standard rolling-average formulation.
    """
    if window <= 0:
        raise ValueError("window must be greater than zero")

    delta = series.diff()

    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    average_gain = gains.rolling(window=window).mean()
    average_loss = losses.rolling(window=window).mean()

    relative_strength = average_gain / average_loss

    return 100 - (100 / (1 + relative_strength))


def rolling_high_low_range(
        high: pd.Series,
        low: pd.Series,
        window: int = 20,
) -> pd.Series:
    """
    Calculate the rolling high-low range as a percentage of price.

    Formula:
        (rolling_high - rolling_low) / rolling_low
    """
    if window <= 0:
        raise ValueError("window must be greater than zero")

    rolling_high = high.rolling(window=window).max()
    rolling_low = low.rolling(window=window).min()

    return (rolling_high - rolling_low) / rolling_low


def volume_ratio(
        volume: pd.Series,
        window: int = 20,
) -> pd.Series:
    """
    Compare current volume with its rolling average.

    Example:
        1.50 means current volume is approximately
        1.5 times the rolling average.
    """
    if window <= 0:
        raise ValueError("window must be greater than zero")

    average_volume = volume.rolling(window=window).mean()

    return volume / average_volume


def moving_average_slope(
        series: pd.Series,
        window: int,
        slope_periods: int = 5,
) -> pd.Series:
    """
    Calculate the percentage change in a moving average.

    This is a simple, interpretable slope proxy.

    Example:
        MA50 today compared with MA50 five sessions ago.
    """
    ma = moving_average(series, window)

    return (ma / ma.shift(slope_periods)) - 1.0