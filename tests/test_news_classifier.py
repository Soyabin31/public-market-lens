from marketlens.news.classifier import classify_article


def test_us_macro_article_is_classified_as_us() -> None:
    result = classify_article(
        source="Economic Times Markets",
        url=(
            "https://economictimes.indiatimes.com/"
            "markets/us-stocks/wall-street-guide/"
            "us-economy-firming"
        ),
        title=(
            "US economy firming as inflation risks persist, "
            "says Richmond Fed's Tom Barkin"
        ),
        summary=(
            "Richmond Fed President Tom Barkin discusses "
            "inflation and the US economy."
        ),
    )

    assert result.market == "us"
    assert result.geography == "US"
    assert result.asset_class == "macro"
    assert result.category == "macro"


def test_nifty_article_is_classified_as_india() -> None:
    result = classify_article(
        source="Mint Markets",
        url="https://www.livemint.com/market/nifty-50",
        title=(
            "Nifty 50 deep-dive guide for investors: "
            "Bearish engulfing candlestick"
        ),
        summary=(
            "The Nifty 50 paused its recovery "
            "after facing selling pressure."
        ),
    )

    assert result.market == "india"
    assert result.geography == "IN"
    assert result.asset_class == "index"
    assert result.category == "market"


def test_crypto_article_is_classified_as_crypto() -> None:
    result = classify_article(
        source="Investing.com India",
        url=(
            "https://in.investing.com/news/"
            "cryptocurrency-news/eos-climbs"
        ),
        title="EOS Climbs 12.12% In Bullish Trade",
        summary=None,
    )

    assert result.market == "crypto"
    assert result.geography == "GLOBAL"
    assert result.asset_class == "crypto"
    assert result.category == "crypto"


def test_unknown_article_is_classified_as_global() -> None:
    result = classify_article(
        source="Example Source",
        url="https://example.com/article",
        title="Global economic developments",
        summary="Markets react to international developments.",
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.asset_class == "unknown"
    assert result.category == "general"


def test_india_headline_beats_incidental_us_treasury_signal():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/markets/india-bonds",
        title="India bonds pummelled after Treasury rout",
        summary="Indian bonds declined as global yields moved higher.",
    )

    assert result.market == "india"
    assert result.geography == "IN"
    assert result.category == "macro"
    assert result.asset_class == "macro"


def test_us_stock_headline_is_not_misclassified_as_india():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/markets/us-stocks",
        title="US stocks: MGM Resorts shares plunge 10%",
        summary="Shares of MGM Resorts declined sharply.",
    )

    assert result.market == "us"
    assert result.geography == "US"
    assert result.category == "market"
    assert result.asset_class == "equity"


def test_global_market_japan_is_not_classified_as_india_or_us():
    result = classify_article(
        source="Business Standard",
        url="https://example.com/global-markets",
        title="Global Market: Japan's Nikkei falls as investors assess economic outlook",
        summary="Japanese equities declined.",
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.category == "market"
    assert result.asset_class == "index"


def test_global_market_eurozone_is_global():
    result = classify_article(
        source="Business Standard",
        url="https://example.com/global-markets",
        title="Global Market: Eurozone bond selloff intensifies",
        summary="European bond yields moved higher.",
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.category == "macro"
    assert result.asset_class == "macro"


def test_global_market_boE_is_global():
    result = classify_article(
        source="Business Standard",
        url="https://example.com/global-markets",
        title="Global Market: BoE signals cautious approach",
        summary="The Bank of England discussed monetary policy.",
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.category == "policy"
    assert result.asset_class == "unknown"


def test_indian_company_story_is_company_not_macro():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/markets/company",
        title="Voltas's market share is growing",
        summary="The company continues to expand its business.",
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.category == "company"
    assert result.asset_class == "equity"


def test_reliance_fundraise_is_company_not_macro():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/markets/company",
        title="Billionaire Ambani's Reliance Industries eyes debt fundraise",
        summary="The company is considering a debt fundraise.",
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.category == "company"
    assert result.asset_class == "equity"


def test_crypto_has_priority_over_geography():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/crypto",
        title="Bitcoin rises as US investors return to crypto",
        summary="Crypto markets gained.",
    )

    assert result.market == "crypto"
    assert result.geography == "GLOBAL"
    assert result.category == "crypto"
    assert result.asset_class == "crypto"


def test_india_index_headline_is_index_market():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/markets/nifty",
        title="Sensex and Nifty crash today",
        summary="Indian benchmark indices fell sharply.",
    )

    assert result.market == "india"
    assert result.geography == "IN"
    assert result.category == "market"
    assert result.asset_class == "index"


def test_us_macro_headline_is_us_macro():
    result = classify_article(
        source="Business Standard",
        url="https://example.com/us-economy",
        title="US inflation data keeps investors focused on Fed rate cuts",
        summary="The Federal Reserve remains central to market expectations.",
    )

    assert result.market == "us"
    assert result.geography == "US"
    assert result.category == "macro"
    assert result.asset_class == "macro"


def test_company_jobs_story_is_company_not_macro():
    result = classify_article(
        source="Business Standard",
        url="https://example.com/company",
        title="Myntra creates 26,000 seasonal jobs",
        summary="The company is preparing for the festive shopping season.",
    )

    assert result.category == "company"
    assert result.asset_class == "equity"


def test_unknown_article_remains_conservative():
    result = classify_article(
        source="Unknown Source",
        url="https://example.com/story",
        title="New technology changes the industry",
        summary="The development attracted attention from businesses.",
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.category == "general"
    assert result.asset_class == "unknown"

def test_us_stocks_with_fed_rate_hike_context_are_macro():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/us-stocks-rate-hike",
        title=(
            "US stocks face rate-hike jitters as investors "
            "assess Fed's policy path"
        ),
        summary=None,
    )

    assert result.market == "us"
    assert result.geography == "US"
    assert result.category == "macro"
    assert result.asset_class == "macro"


def test_market_wrap_with_gainers_and_losers_is_market_index():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/market-wrap",
        title=(
            "Market wrap: Cipla, ONGC, HDFC Life, Bajaj Finance "
            "top gainers and losers on Nifty and Sensex"
        ),
        summary=None,
    )

    assert result.market == "india"
    assert result.geography == "IN"
    assert result.category == "market"
    assert result.asset_class == "index"


def test_stock_market_prediction_with_nifty_sensex_is_market_index():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/stock-market-prediction",
        title=(
            "Stock market prediction for tomorrow: "
            "Sensex, Nifty outlook"
        ),
        summary=None,
    )

    assert result.market == "india"
    assert result.geography == "IN"
    assert result.category == "market"
    assert result.asset_class == "index"


def test_market_trading_guide_is_market_equity():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/trading-guide",
        title=(
            "Market Trading Guide: Finolex Cables among "
            "3 stock recommendations"
        ),
        summary=None,
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.category == "market"
    assert result.asset_class == "equity"


def test_nasdaq_record_high_is_market_index():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/nasdaq-record",
        title=(
            "US stock market today: Nasdaq hits another record high"
        ),
        summary=None,
    )

    assert result.market == "us"
    assert result.geography == "US"
    assert result.category == "market"
    assert result.asset_class == "index"


def test_nikkei_rise_is_market_index():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/nikkei-rise",
        title=(
            "Global Market: Japan's Nikkei rises "
            "as investors assess economic outlook"
        ),
        summary=None,
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.category == "market"
    assert result.asset_class == "index"


def test_nifty_deep_dive_is_market_index():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/nifty-deep-dive",
        title="Nifty 50 deep-dive: what investors need to know",
        summary=None,
    )

    assert result.market == "india"
    assert result.geography == "IN"
    assert result.category == "market"
    assert result.asset_class == "index"


def test_european_shares_edge_lower_is_market_equity():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/european-shares",
        title=(
            "Global Market: European shares edge lower "
            "as investors assess the outlook"
        ),
        summary=None,
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.category == "market"
    assert result.asset_class == "equity"


def test_india_bonds_pummelled_after_treasury_rout_are_macro():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/india-bonds",
        title="India bonds pummelled after Treasury rout",
        summary=None,
    )

    assert result.market == "india"
    assert result.geography == "IN"
    assert result.category == "macro"
    assert result.asset_class == "macro"


def test_eurozone_bond_selloff_is_global_macro():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/eurozone-bonds",
        title="Global Market: Eurozone bond selloff intensifies",
        summary=None,
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.category == "macro"
    assert result.asset_class == "macro"


def test_boe_cautious_approach_is_policy():
    result = classify_article(
        source="Economic Times",
        url="https://example.com/boe-policy",
        title="Global Market: BoE signals cautious approach",
        summary=None,
    )

    assert result.market == "global"
    assert result.geography == "GLOBAL"
    assert result.category == "policy"
    assert result.asset_class == "unknown"