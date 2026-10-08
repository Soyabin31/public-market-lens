from __future__ import annotations

import pytest

from marketlens.fund import (
    AMFILookThroughEngine,
    FundCatalystScore,
    FundHoldingItem,
    FundPortfolioDisclosure,
    TacticalRotationAdvice,
)


def _make_sample_funds() -> tuple[FundPortfolioDisclosure, FundPortfolioDisclosure]:
    # Fund 1: Flexi Cap Fund with diversified holdings
    fund_flexi = FundPortfolioDisclosure(
        fund_id="ppfas_flexi",
        fund_name="Parag Parikh Flexi Cap Fund",
        amc="PPFAS Mutual Fund",
        disclosure_month="2026-01",
        aum_crores=55_000.0,
        category="Flexi Cap",
        holdings=(
            FundHoldingItem(
                stock_symbol="HDFCBANK",
                company_name="HDFC Bank Ltd",
                sector="Banking",
                weight_pct=8.5,
            ),
            FundHoldingItem(
                stock_symbol="TATAMOTORS",
                company_name="Tata Motors Ltd",
                sector="Automobile",
                weight_pct=7.0,
            ),
            FundHoldingItem(
                stock_symbol="INFY",
                company_name="Infosys Ltd",
                sector="IT",
                weight_pct=6.0,
            ),
            FundHoldingItem(
                stock_symbol="ITC",
                company_name="ITC Ltd",
                sector="FMCG",
                weight_pct=5.5,
            ),
        ),
    )

    # Fund 2: Auto & Chemical thematic fund
    fund_thematic = FundPortfolioDisclosure(
        fund_id="auto_chem_thematic",
        fund_name="Thematic Manufacturing Fund",
        amc="Alpha Mutual Fund",
        disclosure_month="2026-01",
        aum_crores=4_200.0,
        category="Thematic",
        holdings=(
            FundHoldingItem(
                stock_symbol="TATAMOTORS",
                company_name="Tata Motors Ltd",
                sector="Automobile",
                weight_pct=9.5,
            ),
            FundHoldingItem(
                stock_symbol="CHEMCORP",
                company_name="Chemical Corp Ltd",
                sector="Chemicals",
                weight_pct=8.0,
            ),
        ),
    )

    return fund_flexi, fund_thematic


def test_fund_portfolio_disclosure_metrics() -> None:
    fund_flexi, _ = _make_sample_funds()
    assert fund_flexi.stock_count == 4
    # Total concentration of all 4 stocks (which is < 10): 8.5 + 7.0 + 6.0 + 5.5 = 27.0%
    assert fund_flexi.top_10_concentration_pct == 27.0

    breakdown = fund_flexi.get_sector_breakdown()
    assert breakdown["Banking"] == 8.5
    assert breakdown["Automobile"] == 7.0
    assert breakdown["IT"] == 6.0
    assert breakdown["FMCG"] == 5.5


def test_amfi_lookthrough_catalyst_scoring_and_ranking() -> None:
    engine = AMFILookThroughEngine()
    fund_flexi, fund_thematic = _make_sample_funds()
    engine.register_disclosure(fund_flexi)
    engine.register_disclosure(fund_thematic)

    # Live market news sentiments:
    # TATAMOTORS: massive positive (+0.90) due to UK merger & EV growth
    # HDFCBANK: positive (+0.70) due to retail loan turnaround
    # CHEMCORP: extreme negative (-0.85) due to plant fire / export ban
    stock_sentiments = {
        "TATAMOTORS": 0.90,
        "HDFCBANK": 0.70,
        "CHEMCORP": -0.85,
    }
    headlines = {
        "TATAMOTORS": "Tata Motors completes UK restructuring with record EV margin surge.",
        "HDFCBANK": "Board approves retail expansion and merger synergies.",
        "CHEMCORP": "Major production disruption after plant fire incident.",
    }

    # 1. Analyze Flexi Cap Fund
    score_flexi = engine.analyze_fund_catalysts("ppfas_flexi", stock_sentiments, headlines)
    assert isinstance(score_flexi, FundCatalystScore)
    # Expected weighted impacts:
    # HDFCBANK: (8.5 / 100) * 0.70 = 0.0595
    # TATAMOTORS: (7.0 / 100) * 0.90 = 0.0630
    # Net catalyst score: 0.0595 + 0.0630 = +0.1225
    assert score_flexi.net_catalyst_score == pytest.approx(0.1225, abs=1e-4)
    assert score_flexi.covered_holdings_weight_pct == pytest.approx(15.5)
    assert len(score_flexi.top_positive_contributors) == 2
    assert len(score_flexi.top_negative_drags) == 0
    assert "Automobile" in score_flexi.sector_tailwinds
    assert "Banking" in score_flexi.sector_tailwinds

    # 2. Analyze Thematic Fund
    # TATAMOTORS: (9.5 / 100) * 0.90 = +0.0855
    # CHEMCORP: (8.0 / 100) * -0.85 = -0.0680
    # Net score: 0.0855 - 0.0680 = +0.0175
    score_thematic = engine.analyze_fund_catalysts("auto_chem_thematic", stock_sentiments, headlines)
    assert score_thematic.net_catalyst_score == pytest.approx(0.0175, abs=1e-4)
    assert len(score_thematic.top_negative_drags) == 1
    assert score_thematic.top_negative_drags[0].stock_symbol == "CHEMCORP"

    # 3. Rank funds: Flexi Cap should rank higher (+0.1225 vs +0.0175)
    ranked = engine.rank_funds_by_catalyst(stock_sentiments, headlines)
    assert len(ranked) == 2
    assert ranked[0].fund_id == "ppfas_flexi"
    assert ranked[1].fund_id == "auto_chem_thematic"

    # Test dict serialization
    d = score_flexi.to_dict()
    assert d["fund_id"] == "ppfas_flexi"
    assert d["net_catalyst_score"] == pytest.approx(0.1225, abs=1e-4)
    assert len(d["top_positive_contributors"]) == 2


def test_tactical_rotation_advice_generation() -> None:
    engine = AMFILookThroughEngine()
    fund_flexi, fund_thematic = _make_sample_funds()
    engine.register_disclosure(fund_flexi)
    engine.register_disclosure(fund_thematic)

    # Shocks: Chemical sector severe crash, Auto modest, Banking neutral
    stock_sentiments = {
        "TATAMOTORS": 0.10,
        "CHEMCORP": -0.90,  # Drags thematic fund into negative territory
        "HDFCBANK": 0.80,   # Powers Flexi Cap
    }

    advice_list = engine.generate_tactical_rotation_advice(stock_sentiments)
    assert len(advice_list) == 2

    # Flexi cap: HDFC Bank +0.80 * 8.5% = +0.068 -> TACTICAL_ACCUMULATE
    flexi_adv = next(a for a in advice_list if a.fund_id == "ppfas_flexi")
    assert flexi_adv.current_action == "TACTICAL_ACCUMULATE"
    assert flexi_adv.confidence > 0.70
    assert flexi_adv.suggested_alternative is None

    # Thematic fund: Tata Motors (+0.10 * 9.5% = +0.0095), ChemCorp (-0.90 * 8% = -0.072)
    # Net: 0.0095 - 0.072 = -0.0625 -> TACTICAL_DEFENSIVE_ROTATION
    thematic_adv = next(a for a in advice_list if a.fund_id == "auto_chem_thematic")
    assert thematic_adv.current_action == "TACTICAL_DEFENSIVE_ROTATION"
    assert thematic_adv.suggested_alternative is not None
    assert "Stable Money FDs" in thematic_adv.suggested_alternative
