import pandas as pd
import pytest

from marketlens.indicators import (
    distance_from_moving_average,
    moving_average,
    moving_average_slope,
    percentage_return,
    rate_of_change,
    realised_volatility,
    rolling_high_low_range,
    rsi,
    volume_ratio,
)


@pytest.fixture
def sample_prices() -> pd.Series:
    return pd.Series(
        [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        dtype=float,
    )


def test_percentage_return(sample_prices):
    result = percentage_return(sample_prices)

    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == pytest.approx(0.01)


def test_moving_average(sample_prices):
    result = moving_average(sample_prices, window=3)

    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(101.0)
    assert result.iloc[3] == pytest.approx(102.0)


def test_distance_from_moving_average(sample_prices):
    result = distance_from_moving_average(
        sample_prices,
        window=3,
    )

    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(
        102 / 101 - 1
    )


def test_rate_of_change(sample_prices):
    result = rate_of_change(
        sample_prices,
        periods=2,
    )

    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(0.02)


def test_rsi(sample_prices):
    result = rsi(
        sample_prices,
        window=3,
    )

    # Prices rise continuously, therefore RSI should
    # eventually approach 100.
    assert result.iloc[-1] == pytest.approx(100.0)


def test_realised_volatility(sample_prices):
    returns = percentage_return(sample_prices)

    result = realised_volatility(
        returns,
        window=3,
    )

    assert pd.isna(result.iloc[2])
    assert result.iloc[-1] >= 0


def test_rolling_high_low_range(sample_prices):
    high = sample_prices + 1
    low = sample_prices - 1

    result = rolling_high_low_range(
        high,
        low,
        window=3,
    )

    assert pd.isna(result.iloc[1])
    assert result.iloc[-1] > 0


def test_volume_ratio():
    volume = pd.Series(
        [100, 100, 100, 200, 200],
        dtype=float,
    )

    result = volume_ratio(
        volume,
        window=3,
    )

    assert result.iloc[-1] == pytest.approx(1.2)


def test_moving_average_slope(sample_prices):
    result = moving_average_slope(
        sample_prices,
        window=3,
        slope_periods=2,
    )

    assert pd.isna(result.iloc[3])
    assert result.iloc[-1] > 0