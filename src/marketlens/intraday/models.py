from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IntradayCandle:
    """
    Represents one completed OHLCV candle.

    All pattern detection is performed on completed candles.
    This prevents the detector from using information from a
    candle that has not closed yet.
    """

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body(self) -> float:
        """
        Absolute size of the candle body.
        """

        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        """
        Full high-low range of the candle.
        """

        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        """
        Distance between the candle body high and candle high.
        """

        body_high = max(self.open, self.close)

        return self.high - body_high

    @property
    def lower_wick(self) -> float:
        """
        Distance between the candle low and candle body low.
        """

        body_low = min(self.open, self.close)

        return body_low - self.low

    @property
    def is_bullish(self) -> bool:
        """
        True when the candle closes above its open.
        """

        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """
        True when the candle closes below its open.
        """

        return self.close < self.open

    @property
    def is_doji(self) -> bool:
        """
        True when the candle has effectively no body.

        The detector intentionally uses a simple geometric
        definition at this stage. More sophisticated adaptive
        thresholds will be added later.
        """

        if self.range <= 0:
            return False

        return self.body <= self.range * 0.10