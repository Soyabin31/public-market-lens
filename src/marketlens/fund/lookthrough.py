from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence


@dataclass(frozen=True)
class FundHoldingItem:
    """
    Individual stock holding constituent within a mutual fund portfolio.
    """

    stock_symbol: str
    company_name: str
    sector: str
    weight_pct: float  # e.g. 8.45% of total fund AUM
    shares_held: int = 0
    mom_change_shares_pct: float = 0.0  # Month-over-month position change (+/- %)


@dataclass(frozen=True)
class FundPortfolioDisclosure:
    """
    Official monthly AMC portfolio holding disclosure mandated by SEBI.
    """

    fund_id: str
    fund_name: str
    amc: str
    disclosure_month: str  # YYYY-MM (e.g. '2026-01')
    aum_crores: float
    category: str  # e.g. 'Flexi Cap', 'Small Cap', 'Large & Mid Cap'
    holdings: tuple[FundHoldingItem, ...]

    @property
    def stock_count(self) -> int:
        return len(self.holdings)

    @property
    def top_10_concentration_pct(self) -> float:
        sorted_weights = sorted([h.weight_pct for h in self.holdings], reverse=True)
        return round(sum(sorted_weights[:10]), 2)

    def get_sector_breakdown(self) -> dict[str, float]:
        """
        Aggregate total weight percentage allocated to each industry sector.
        """
        breakdown: dict[str, float] = {}
        for h in self.holdings:
            sec = h.sector.strip()
            breakdown[sec] = round(breakdown.get(sec, 0.0) + h.weight_pct, 2)
        return dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True))


@dataclass(frozen=True)
class HoldingCatalystImpact:
    """
    Impact contribution of a specific stock holding on the overall fund.
    """

    stock_symbol: str
    company_name: str
    sector: str
    weight_pct: float
    news_sentiment_score: float  # -1.0 (extreme negative) to +1.0 (extreme positive)
    weighted_impact: float  # (weight_pct / 100.0) * news_sentiment_score
    headline_catalyst: str = ""


@dataclass(frozen=True)
class FundCatalystScore:
    """
    Synthesized look-through score evaluating real-time news impact on a mutual fund.
    """

    fund_id: str
    fund_name: str
    amc: str
    category: str
    disclosure_month: str
    net_catalyst_score: float  # -1.0 to +1.0 (positive indicates net tailwind)
    covered_holdings_weight_pct: float  # Total % of portfolio with active news coverage
    top_positive_contributors: tuple[HoldingCatalystImpact, ...]
    top_negative_drags: tuple[HoldingCatalystImpact, ...]
    sector_tailwinds: tuple[str, ...]
    sector_headwinds: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "fund_id": self.fund_id,
            "fund_name": self.fund_name,
            "amc": self.amc,
            "category": self.category,
            "disclosure_month": self.disclosure_month,
            "net_catalyst_score": round(self.net_catalyst_score, 4),
            "covered_holdings_weight_pct": round(self.covered_holdings_weight_pct, 2),
            "top_positive_contributors": [
                {
                    "symbol": c.stock_symbol,
                    "company": c.company_name,
                    "weight_pct": round(c.weight_pct, 2),
                    "sentiment": round(c.news_sentiment_score, 2),
                    "weighted_impact": round(c.weighted_impact, 4),
                    "catalyst": c.headline_catalyst,
                }
                for c in self.top_positive_contributors
            ],
            "top_negative_drags": [
                {
                    "symbol": d.stock_symbol,
                    "company": d.company_name,
                    "weight_pct": round(d.weight_pct, 2),
                    "sentiment": round(d.news_sentiment_score, 2),
                    "weighted_impact": round(d.weighted_impact, 4),
                    "catalyst": d.headline_catalyst,
                }
                for d in self.top_negative_drags
            ],
            "sector_tailwinds": list(self.sector_tailwinds),
            "sector_headwinds": list(self.sector_headwinds),
        }


@dataclass(frozen=True)
class TacticalRotationAdvice:
    """
    Actionable asset allocation recommendation based on look-through catalyst dynamics.
    """

    fund_id: str
    fund_name: str
    current_action: str  # 'TACTICAL_ACCUMULATE', 'HOLD', 'TACTICAL_DEFENSIVE_ROTATION'
    confidence: float
    time_horizon: str  # '1_TO_3_MONTHS', '3_TO_6_MONTHS'
    reasoning: str
    suggested_alternative: str | None = None  # e.g., 'Stable Money FDs (Fixed Deposit)' or defensive fund


class AMFILookThroughEngine:
    """
    AMFI Portfolio Look-Through & Real-Time News Catalyst Radar.

    Correlates official monthly AMC portfolio holdings with live news sentiment:
    1. Evaluates underlying constituent exposures (e.g. Parag Parikh holding 8.5% HDFC Bank).
    2. Weights real-time breaking news catalysts across all portfolio constituents.
    3. Detects early fund outperformance or upcoming NAV drag days before official monthly sheets update.
    4. Formulates tactical rotation advice (e.g. rotating out of impacted funds into Stable Money FDs).
    """

    def __init__(self) -> None:
        self._disclosures: dict[str, FundPortfolioDisclosure] = {}

    def register_disclosure(self, disclosure: FundPortfolioDisclosure) -> None:
        """
        Register or update a mutual fund monthly disclosure sheet.
        """
        self._disclosures[disclosure.fund_id] = disclosure

    def get_disclosure(self, fund_id: str) -> FundPortfolioDisclosure | None:
        return self._disclosures.get(fund_id)

    def analyze_fund_catalysts(
        self,
        fund_id: str,
        stock_sentiments: dict[str, float],
        catalyst_headlines: dict[str, str] | None = None,
    ) -> FundCatalystScore:
        """
        Analyze news sentiment impact on a specific fund's portfolio holdings.
        """
        disclosure = self.get_disclosure(fund_id)
        if disclosure is None:
            raise KeyError(f"Fund ID '{fund_id}' not found in registered disclosures.")

        headlines = catalyst_headlines or {}
        impacts: list[HoldingCatalystImpact] = []
        covered_weight = 0.0

        for h in disclosure.holdings:
            sym = h.stock_symbol.strip().upper()
            if sym in stock_sentiments:
                sentiment = stock_sentiments[sym]  # -1.0 to +1.0
                # Weighted impact = (weight_pct / 100.0) * sentiment
                w_impact = (h.weight_pct / 100.0) * sentiment
                impacts.append(
                    HoldingCatalystImpact(
                        stock_symbol=sym,
                        company_name=h.company_name,
                        sector=h.sector,
                        weight_pct=h.weight_pct,
                        news_sentiment_score=sentiment,
                        weighted_impact=w_impact,
                        headline_catalyst=headlines.get(sym, ""),
                    )
                )
                covered_weight += h.weight_pct

        # Sort positive contributors and negative drags
        positives = sorted([i for i in impacts if i.weighted_impact > 0], key=lambda x: x.weighted_impact, reverse=True)
        negatives = sorted([i for i in impacts if i.weighted_impact < 0], key=lambda x: x.weighted_impact)

        net_score = sum(i.weighted_impact for i in impacts)

        # Sector level tailwinds & headwinds
        sector_impacts: dict[str, float] = {}
        for imp in impacts:
            sector_impacts[imp.sector] = sector_impacts.get(imp.sector, 0.0) + imp.weighted_impact

        tailwinds = tuple(sec for sec, val in sector_impacts.items() if val > 0.01)
        headwinds = tuple(sec for sec, val in sector_impacts.items() if val < -0.01)

        return FundCatalystScore(
            fund_id=disclosure.fund_id,
            fund_name=disclosure.fund_name,
            amc=disclosure.amc,
            category=disclosure.category,
            disclosure_month=disclosure.disclosure_month,
            net_catalyst_score=net_score,
            covered_holdings_weight_pct=covered_weight,
            top_positive_contributors=tuple(positives[:5]),
            top_negative_drags=tuple(negatives[:5]),
            sector_tailwinds=tailwinds,
            sector_headwinds=headwinds,
        )

    def rank_funds_by_catalyst(
        self,
        stock_sentiments: dict[str, float],
        catalyst_headlines: dict[str, str] | None = None,
    ) -> list[FundCatalystScore]:
        """
        Rank all registered mutual funds by net positive catalyst score.
        """
        scores: list[FundCatalystScore] = []
        for f_id in self._disclosures:
            score = self.analyze_fund_catalysts(
                fund_id=f_id,
                stock_sentiments=stock_sentiments,
                catalyst_headlines=catalyst_headlines,
            )
            scores.append(score)

        scores.sort(key=lambda s: s.net_catalyst_score, reverse=True)
        return scores

    def generate_tactical_rotation_advice(
        self,
        stock_sentiments: dict[str, float],
        catalyst_headlines: dict[str, str] | None = None,
    ) -> list[TacticalRotationAdvice]:
        """
        Formulate tactical asset allocation and rotation advice across all funds.
        """
        ranked = self.rank_funds_by_catalyst(stock_sentiments, catalyst_headlines)
        recommendations: list[TacticalRotationAdvice] = []

        for score in ranked:
            if score.net_catalyst_score >= 0.03:
                action = "TACTICAL_ACCUMULATE"
                conf = min(0.65 + (score.net_catalyst_score * 3.0), 0.95)
                top_syms = ", ".join(c.stock_symbol for c in score.top_positive_contributors[:3])
                reason = (
                    f"Strong net positive news tailwinds (Score: +{score.net_catalyst_score:.4f}) "
                    f"driven by high-conviction holdings ({top_syms}). Expect 1–3 month tactical outperformance."
                )
                alt = None
            elif score.net_catalyst_score <= -0.02:
                action = "TACTICAL_DEFENSIVE_ROTATION"
                conf = min(0.65 + (abs(score.net_catalyst_score) * 3.0), 0.95)
                drag_syms = ", ".join(d.stock_symbol for d in score.top_negative_drags[:3])
                reason = (
                    f"Significant negative news headwinds (Score: {score.net_catalyst_score:.4f}) "
                    f"driven by heavily impacted constituents ({drag_syms}). "
                    f"Downside NAV pressure anticipated over coming weeks."
                )
                alt = "Stable Money FDs (Fixed Deposit at 8.5% guaranteed) or Liquid Overnight Fund"
            else:
                action = "HOLD"
                conf = 0.60
                reason = (
                    f"Neutral net catalyst balance (Score: {score.net_catalyst_score:+.4f}). "
                    f"Maintain systematic monthly SIP allocation."
                )
                alt = None

            recommendations.append(
                TacticalRotationAdvice(
                    fund_id=score.fund_id,
                    fund_name=score.fund_name,
                    current_action=action,
                    confidence=round(conf, 2),
                    time_horizon="1_TO_3_MONTHS",
                    reasoning=reason,
                    suggested_alternative=alt,
                )
            )

        return recommendations
