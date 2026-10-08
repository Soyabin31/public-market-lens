from __future__ import annotations

import pytest

from marketlens.fund import (
    CatalystEvent,
    DeepValueOpportunityHunter,
    MutualFundHolding,
    OpportunityCandidate,
    StockValuationSnapshot,
)


def test_stock_valuation_snapshot_properties() -> None:
    # HDFC Bank scenario: trading at 750, 52w high 1500, 52w low 700, ATH 1600
    snap = StockValuationSnapshot(
        symbol="HDFCBANK",
        company_name="HDFC Bank Ltd",
        current_price=750.0,
        week_52_high=1500.0,
        week_52_low=700.0,
        historical_high=1600.0,
        sector="Banking",
        pe_ratio=14.5,
    )
    # Discount from 52w high: (1500 - 750) / 1500 = 50.0%
    assert snap.discount_from_52w_high_pct == 50.0
    # Distance from 52w low: (750 - 700) / 700 = 7.14%
    assert snap.distance_from_52w_low_pct == pytest.approx(7.1428, abs=1e-3)
    # Discount from ATH: (1600 - 750) / 1600 = 53.125%
    assert snap.discount_from_ath_pct == pytest.approx(53.125, abs=1e-3)
    # Near 52w low (within 15%) and > 30% discount -> deep value discount
    assert snap.is_deep_value_discount


def test_deep_value_opportunity_hunter_scan_and_confluence() -> None:
    hunter = DeepValueOpportunityHunter(min_discount_pct=25.0, min_catalyst_sentiment=0.65)

    stocks = [
        # Stock 1: HDFC Bank - deep discount + near 52w low
        StockValuationSnapshot(
            symbol="HDFCBANK",
            company_name="HDFC Bank Ltd",
            current_price=750.0,
            week_52_high=1500.0,
            week_52_low=720.0,
            historical_high=1600.0,
            sector="Banking",
        ),
        # Stock 2: Bank of Maharashtra - turnaround candidate
        StockValuationSnapshot(
            symbol="MAHABANK",
            company_name="Bank of Maharashtra",
            current_price=55.0,
            week_52_high=100.0,
            week_52_low=50.0,
            historical_high=120.0,
            sector="Banking",
        ),
        # Stock 3: High flyer trading near ATH (Not a discount)
        StockValuationSnapshot(
            symbol="TITAN",
            company_name="Titan Company",
            current_price=3700.0,
            week_52_high=3800.0,
            week_52_low=2800.0,
            historical_high=3800.0,
            sector="Consumer",
        ),
        # Stock 4: Deep discount BUT NO positive catalyst (Value trap)
        StockValuationSnapshot(
            symbol="TROUBLED",
            company_name="Troubled Corp",
            current_price=40.0,
            week_52_high=100.0,
            week_52_low=35.0,
            historical_high=150.0,
            sector="Telecom",
        ),
    ]

    catalysts = [
        CatalystEvent(
            event_id="cat_1",
            symbol="HDFCBANK",
            event_type="management_turnaround",
            headline="Board approves strategic merger synergy and aggressive retail lending revival.",
            sentiment_score=0.88,
            expected_impact="HIGH_POSITIVE",
        ),
        CatalystEvent(
            event_id="cat_2",
            symbol="MAHABANK",
            event_type="capital_infusion",
            headline="Bank reports record quarterly profit surge and NPA reduction.",
            sentiment_score=0.82,
            expected_impact="HIGH_POSITIVE",
        ),
        # Negative/neutral news should be filtered out
        CatalystEvent(
            event_id="cat_3",
            symbol="TROUBLED",
            event_type="litigation",
            headline="Lawsuit filed regarding debt covenants.",
            sentiment_score=0.20,
            expected_impact="HIGH_NEGATIVE",
        ),
    ]

    fund_holdings = [
        MutualFundHolding(
            fund_name="Parag Parikh Flexi Cap Fund",
            amc="PPFAS Mutual Fund",
            scheme_code="122639",
            stock_symbol="HDFCBANK",
            weight_pct=8.45,
        ),
        MutualFundHolding(
            fund_name="Nippon India Small Cap Fund",
            amc="Nippon India Mutual Fund",
            scheme_code="118778",
            stock_symbol="MAHABANK",
            weight_pct=4.20,
        ),
    ]

    opps = hunter.scan_opportunities(stocks=stocks, catalysts=catalysts, fund_holdings=fund_holdings)

    # TITAN rejected (not a discount)
    # TROUBLED rejected (no positive catalyst > 0.65)
    # Only HDFCBANK and MAHABANK qualified
    assert len(opps) == 2

    # Check top candidate
    top = opps[0]
    assert top.symbol in {"HDFCBANK", "MAHABANK"}
    assert top.confluence_score > 0.65
    assert len(top.catalysts) == 1
    assert top.catalysts[0].sentiment_score >= 0.80
    assert len(top.associated_mutual_funds) == 1
    assert "narrative_summary" in top.to_dict()

    # Verify mutual fund look-through link
    hdfc_opp = next(o for o in opps if o.symbol == "HDFCBANK")
    assert hdfc_opp.associated_mutual_funds[0]["fund_name"] == "Parag Parikh Flexi Cap Fund"
    assert hdfc_opp.associated_mutual_funds[0]["weight_pct"] == 8.45
