from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence


@dataclass(frozen=True)
class StockValuationSnapshot:
    """
    Fundamental and price valuation snapshot of a company.
    """

    symbol: str
    company_name: str
    current_price: float
    week_52_high: float
    week_52_low: float
    historical_high: float
    sector: str
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    market_cap_cr: float | None = None

    @property
    def discount_from_52w_high_pct(self) -> float:
        if self.week_52_high <= 0:
            return 0.0
        return max(0.0, (self.week_52_high - self.current_price) / self.week_52_high * 100.0)

    @property
    def distance_from_52w_low_pct(self) -> float:
        if self.week_52_low <= 0:
            return 0.0
        return max(0.0, (self.current_price - self.week_52_low) / self.week_52_low * 100.0)

    @property
    def discount_from_ath_pct(self) -> float:
        if self.historical_high <= 0:
            return 0.0
        return max(0.0, (self.historical_high - self.current_price) / self.historical_high * 100.0)

    @property
    def is_deep_value_discount(self) -> bool:
        # Stock is near 52w low (within 15%) OR down > 30% from 52w high
        return self.distance_from_52w_low_pct <= 15.0 or self.discount_from_52w_high_pct >= 30.0


@dataclass(frozen=True)
class CatalystEvent:
    """
    Positive corporate or macro news catalyst impacting a company.
    """

    event_id: str
    symbol: str
    event_type: str  # 'management_turnaround', 'acquisition', 'capital_infusion', 'earnings_beat'
    headline: str
    sentiment_score: float  # 0.0 to 1.0 (>= 0.65 is positive)
    expected_impact: str  # 'HIGH_POSITIVE', 'MODERATE_POSITIVE'
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(frozen=True)
class MutualFundHolding:
    """
    Holding disclosure of a stock inside a mutual fund scheme.
    """

    fund_name: str
    amc: str
    scheme_code: str
    stock_symbol: str
    weight_pct: float  # e.g. 7.5% of fund AUM


@dataclass(frozen=True)
class OpportunityCandidate:
    """
    Synthesized high-confluence turnaround opportunity.
    """

    symbol: str
    company_name: str
    current_price: float
    sector: str
    discount_from_52w_high_pct: float
    distance_from_52w_low_pct: float
    catalysts: tuple[CatalystEvent, ...]
    catalyst_sentiment_score: float
    confluence_score: float  # 0.0 to 1.0
    recommended_time_horizon: str  # '1_WEEK', '1_MONTH', '3_MONTHS', '6_MONTHS'
    estimated_upside_pct: float
    associated_mutual_funds: tuple[dict[str, Any], ...]
    narrative_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "company_name": self.company_name,
            "current_price": round(self.current_price, 2),
            "sector": self.sector,
            "discount_from_52w_high_pct": round(self.discount_from_52w_high_pct, 2),
            "distance_from_52w_low_pct": round(self.distance_from_52w_low_pct, 2),
            "catalyst_count": len(self.catalysts),
            "catalyst_sentiment_score": round(self.catalyst_sentiment_score, 2),
            "confluence_score": round(self.confluence_score, 4),
            "recommended_time_horizon": self.recommended_time_horizon,
            "estimated_upside_pct": round(self.estimated_upside_pct, 2),
            "associated_mutual_funds": list(self.associated_mutual_funds),
            "narrative_summary": self.narrative_summary,
        }


class DeepValueOpportunityHunter:
    """
    Deep Value & Asymmetric Dip Opportunity Hunter.

    Scans for quality companies at historical discount percentiles (52-week low / ATH discount),
    correlates them with verified positive news catalysts, and aggregates mutual fund exposures
    for high-confluence medium/long-term allocation.
    """

    def __init__(
        self,
        min_discount_pct: float = 20.0,
        min_catalyst_sentiment: float = 0.65,
    ) -> None:
        self._min_discount_pct = min_discount_pct
        self._min_catalyst_sentiment = min_catalyst_sentiment

    def scan_opportunities(
        self,
        stocks: Sequence[StockValuationSnapshot],
        catalysts: Sequence[CatalystEvent],
        fund_holdings: Sequence[MutualFundHolding] | None = None,
    ) -> list[OpportunityCandidate]:
        """
        Scan stock universe, correlate positive catalysts, and rank by confluence score.
        """
        # 1. Group catalysts by symbol
        catalysts_by_symbol: dict[str, list[CatalystEvent]] = {}
        for cat in catalysts:
            sym = cat.symbol.strip().upper()
            if cat.sentiment_score >= self._min_catalyst_sentiment:
                catalysts_by_symbol.setdefault(sym, []).append(cat)

        # 2. Group fund holdings by symbol
        funds_by_symbol: dict[str, list[MutualFundHolding]] = {}
        if fund_holdings:
            for hold in fund_holdings:
                sym = hold.stock_symbol.strip().upper()
                funds_by_symbol.setdefault(sym, []).append(hold)

        opportunities: list[OpportunityCandidate] = []

        for stock in stocks:
            sym = stock.symbol.strip().upper()

            # Must qualify as valuation discount
            if not stock.is_deep_value_discount and stock.discount_from_52w_high_pct < self._min_discount_pct:
                continue

            stock_catalysts = catalysts_by_symbol.get(sym, [])
            if not stock_catalysts:
                continue  # Value without catalyst is a potential value trap; require positive catalyst!

            # Compute catalyst score
            avg_sentiment = float(sum(c.sentiment_score for c in stock_catalysts) / len(stock_catalysts))

            # Compute valuation discount score (normalized 0.0 to 1.0)
            # More discount = higher opportunity, capped at 60% discount
            discount_norm = min(stock.discount_from_52w_high_pct / 60.0, 1.0)

            # Proximity to 52w low bonus (within 5% of low = 1.0, 20% = 0.0)
            low_proximity_bonus = max(0.0, (20.0 - stock.distance_from_52w_low_pct) / 20.0)

            # Confluence Score: Weighted combination of Discount (40%), Low Proximity (20%), Catalyst (40%)
            confluence = (0.40 * discount_norm) + (0.20 * low_proximity_bonus) + (0.40 * avg_sentiment)

            # Horizon & Upside Estimation
            if confluence >= 0.80:
                horizon = "1_MONTH"
                est_upside = min(stock.discount_from_52w_high_pct * 0.6, 35.0)
            elif confluence >= 0.65:
                horizon = "3_MONTHS"
                est_upside = min(stock.discount_from_52w_high_pct * 0.45, 25.0)
            else:
                horizon = "6_MONTHS"
                est_upside = min(stock.discount_from_52w_high_pct * 0.3, 15.0)

            # Associated mutual funds holding this turnaround stock
            related_funds = funds_by_symbol.get(sym, [])
            fund_data = tuple(
                {
                    "fund_name": f.fund_name,
                    "amc": f.amc,
                    "scheme_code": f.scheme_code,
                    "weight_pct": round(f.weight_pct, 2),
                }
                for f in sorted(related_funds, key=lambda x: x.weight_pct, reverse=True)
            )

            # Build narrative
            cat_types = ", ".join({c.event_type for c in stock_catalysts})
            narrative = (
                f"{stock.company_name} ({sym}) is trading at a deep discount "
                f"({stock.discount_from_52w_high_pct:.1f}% below 52W high, near 52W low) "
                f"with strong positive catalyst ({cat_types}, sentiment {avg_sentiment:.2f}). "
                f"Confluence score {confluence:.2f} indicates asymmetric turnaround upside of ~{est_upside:.1f}% "
                f"over a {horizon.replace('_', ' ').lower()} horizon."
            )

            opp = OpportunityCandidate(
                symbol=sym,
                company_name=stock.company_name,
                current_price=stock.current_price,
                sector=stock.sector,
                discount_from_52w_high_pct=stock.discount_from_52w_high_pct,
                distance_from_52w_low_pct=stock.distance_from_52w_low_pct,
                catalysts=tuple(stock_catalysts),
                catalyst_sentiment_score=avg_sentiment,
                confluence_score=confluence,
                recommended_time_horizon=horizon,
                estimated_upside_pct=est_upside,
                associated_mutual_funds=fund_data,
                narrative_summary=narrative,
            )
            opportunities.append(opp)

        # Sort descending by confluence score (highest quality asymmetric setups first)
        opportunities.sort(key=lambda o: o.confluence_score, reverse=True)
        return opportunities
