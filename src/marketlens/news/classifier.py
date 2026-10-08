import re
from dataclasses import dataclass


@dataclass(frozen=True)
class NewsClassification:
    """
    Deterministic coarse classification for a news article.

    The classifier intentionally remains conservative.

    - market/geography: Where is the story primarily focused?
    - category: What is the story primarily about?
    - asset_class: What financial asset/domain does it concern?
    """

    market: str
    geography: str
    asset_class: str
    category: str


def _contains_any(
        text: str,
        indicators: tuple[str, ...],
) -> bool:
    """
    Return True when the text contains at least one indicator.

    Matching is performed using word/phrase boundaries rather than
    simple substring matching.

    This prevents false positives where a short indicator happens
    to appear inside an unrelated word.
    """

    for indicator in indicators:
        pattern = (
                r"(?<!\w)"
                + re.escape(indicator)
                + r"(?!\w)"
        )

        if re.search(
                pattern,
                text,
        ):
            return True

    return False


def classify_article(
        source: str,
        url: str,
        title: str,
        summary: str | None,
) -> NewsClassification:
    """
    Classify an article using deterministic evidence.

    Design principles:

    1. Crypto is identified first.
    2. Geography is determined independently from category.
    3. Title evidence is stronger than summary evidence.
    4. URL evidence is only supporting evidence for geography/crypto.
    5. Category is driven by the article's primary subject.
    6. Explicit market/index stories take precedence over generic
       company indicators.
    7. Strong macro evidence takes precedence over generic company
       evidence.
    8. Central-bank stories are split into macro vs policy depending
       on whether the title contains an explicit macro subject.
    9. Asset class is determined from the final category plus
       explicit financial-asset evidence.
    10. The classifier is intentionally coarse. Rich semantic
        interpretation belongs to the later LLM layer.
    """

    # ------------------------------------------------------------------
    # 0. Normalize input
    # ------------------------------------------------------------------

    title_text = title.lower().strip()

    summary_text = (
        summary.lower().strip()
        if summary
        else ""
    )

    url_text = url.lower().strip()

    title_summary = " ".join(
        [
            title_text,
            summary_text,
        ]
    )

    all_text = " ".join(
        [
            title_text,
            summary_text,
            url_text,
        ]
    )

    # ------------------------------------------------------------------
    # 1. Crypto evidence
    # ------------------------------------------------------------------

    crypto_indicators = (
        "bitcoin",
        "ethereum",
        "crypto",
        "cryptocurrency",
        "cryptocurrencies",
        "token",
        "tokens",
        "altcoin",
        "altcoins",
        "stablecoin",
        "stablecoins",
        "blockchain",
    )

    is_crypto = (
            _contains_any(
                title_summary,
                crypto_indicators,
            )
            or _contains_any(
        url_text,
        crypto_indicators,
    )
    )

    # ------------------------------------------------------------------
    # 2. Geography indicators
    # ------------------------------------------------------------------

    explicit_global_indicators = (
        "global market",
        "global markets",
        "eurozone",
        "european central bank",
        "ecb",
        "bank of england",
        "boe",
        "bank of japan",
        "boj",
        "japan",
        "japanese",
        "nikkei",
        "jgb",
        "china",
        "chinese",
        "hong kong",
        "hang seng",
        "europe",
        "european",
        "germany",
        "german",
        "france",
        "french",
        "italy",
        "italian",
        "spain",
        "spanish",
        "united kingdom",
        "britain",
        "british",
        "uk fiscal",
        "pound",
        "sterling",
    )

    india_indicators = (
        "india",
        "indian",
        "nifty",
        "nifty 50",
        "nifty50",
        "bank nifty",
        "sensex",
        "bse",
        "nse",
        "rbi",
        "sebi",
        "rupee",
        "inr",
        "₹",
        "crore",
        "crores",
        "lakh",
        "lakhs",
        "upi",
        "irda",
        "irdai",
        "gst",
        "india inflation",
        "india gdp",
        "indian government",
        "indian bonds",
        "india bonds",
        "mumbai stock exchange",
        "national stock exchange of india",
    )

    us_indicators = (
        "us economy",
        "u.s. economy",
        "united states",
        "federal reserve",
        "fed rate",
        "fed raises",
        "fed cuts",
        "fed holds",
        "fed decision",
        "fed meeting",
        "wall street",
        "nasdaq",
        "s&p 500",
        "dow jones",
        "treasury yield",
        "treasury yields",
        "us inflation",
        "us jobs",
        "nonfarm payroll",
        "richmond fed",
        "new york fed",
        "sec.gov",
        "us stocks",
        "u.s. stocks",
        "american stocks",
        "american economy",
    )

    # ------------------------------------------------------------------
    # 3. Geography determination
    # ------------------------------------------------------------------

    if is_crypto:
        market = "crypto"
        geography = "GLOBAL"

    elif _contains_any(
            title_text,
            explicit_global_indicators,
    ):
        market = "global"
        geography = "GLOBAL"

    elif _contains_any(
            title_text,
            india_indicators,
    ):
        market = "india"
        geography = "IN"

    elif _contains_any(
            title_text,
            us_indicators,
    ):
        market = "us"
        geography = "US"

    elif _contains_any(
            summary_text,
            india_indicators,
    ):
        market = "india"
        geography = "IN"

    elif _contains_any(
            summary_text,
            us_indicators,
    ):
        market = "us"
        geography = "US"

    elif _contains_any(
            all_text,
            explicit_global_indicators,
    ):
        market = "global"
        geography = "GLOBAL"

    else:
        market = "global"
        geography = "GLOBAL"

    # ------------------------------------------------------------------
    # 4. Category indicators
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 4A. Strong macro subject indicators
    # ------------------------------------------------------------------

    strong_macro_indicators = (
        "inflation",
        "interest rate",
        "interest rates",
        "rate hike",
        "rate hikes",
        "rate cut",
        "rate cuts",
        "rate decision",
        "repo rate",
        "federal reserve",
        "fed rate",
        "fed policy",
        "fed's policy",
        "monetary policy",
        "central bank",
        "gdp",
        "unemployment",
        "nonfarm payroll",
        "treasury yield",
        "treasury yields",
        "economic growth",
        "inflation data",
        "cpi",
        "ppi",
        "bond",
        "bonds",
        "bond yields",
        "bond yield",
        "bond market",
        "bond markets",
        "bond selloff",
        "bond sell-off",
        "bond rally",
        "bond rout",
        "economic data",
    )

    # IMPORTANT:
    # "seasonal jobs" is intentionally NOT here.
    # It is a company/business indicator and belongs below.

    # ------------------------------------------------------------------
    # 4B. Policy / regulatory indicators
    # ------------------------------------------------------------------

    policy_indicators = (
        "rbi",
        "sebi",
        "regulation",
        "regulatory",
        "government policy",
        "policy decision",
        "policy changes",
        "policy change",
        "regulatory changes",
        "regulatory change",
        "new rules",
        "new rule",
        "rule change",
        "dgca",
        "irda",
        "irdai",
        "sec.gov",
    )

    # Central banks are kept separate because their names alone should
    # not automatically make every article a macro article.
    central_bank_policy_indicators = (
        "rbi",
        "sebi",
        "bank of england",
        "boe",
        "bank of japan",
        "boj",
        "european central bank",
        "ecb",
    )

    # ------------------------------------------------------------------
    # 4C. Company-specific indicators
    # ------------------------------------------------------------------

    company_indicators = (
        "earnings",
        "profit",
        "profits",
        "revenue",
        "quarter",
        "quarterly",
        "guidance",
        "merger",
        "mergers",
        "acquisition",
        "acquisitions",
        "acquire",
        "acquired",
        "ipo",
        "fundraise",
        "fundraising",
        "debt fundraise",
        "stake sale",
        "market share",
        "launches",
        "launch",
        "appoints",
        "appointed",
        "partnership",
        "contract",
        "order win",
        "wins contract",
        "deal",
        "seasonal jobs",
        "dividend",
        "dividends",
        "capex",
        "joint venture",
    )

    # ------------------------------------------------------------------
    # 4D. Explicit market / index subject indicators
    #
    # These are deliberately stronger than generic words such as
    # "market", "shares", or "stocks".
    #
    # Nifty / Bank Nifty / Sensex belong here because they are direct
    # evidence that the article concerns the market/index.
    # ------------------------------------------------------------------

    explicit_market_indicators = (
        "nifty",
        "nifty 50",
        "nifty50",
        "bank nifty",
        "sensex",
        "nasdaq",
        "s&p 500",
        "dow jones",
        "nikkei",
        "hang seng",
        "stock market",
        "stock markets",
        "market wrap",
        "market outlook",
        "stock market outlook",
        "stock market today",
        "stock market prediction",
        "stock recommendations",
        "stock picks",
        "nifty outlook",
        "sensex outlook",
        "nifty prediction",
        "sensex prediction",
        "market rally",
        "market selloff",
        "market sell-off",
        "market crash",
        "market correction",
        "market plunge",
        "market surge",
        "stocks tumble",
        "stocks plunge",
        "stocks fall",
        "stocks rise",
        "stocks gain",
        "shares tumble",
        "shares plunge",
        "shares fall",
        "shares rise",
        "shares gain",
        "shares edge lower",
        "shares edge higher",
        "shares decline",
        "european shares",
        "record high",
        "record low",
        "52-week high",
        "52 week high",
        "52-week low",
        "52 week low",
        "day's low",
        "days low",
        "top gainers",
        "top losers",
        "top stocks",
        "breakout stocks",
        "trading guide",
    )

    # ------------------------------------------------------------------
    # 4E. Evaluate evidence
    # ------------------------------------------------------------------

    has_strong_macro = _contains_any(
        title_summary,
        strong_macro_indicators,
    )

    has_policy = _contains_any(
        title_summary,
        policy_indicators,
    )

    has_central_bank_policy = _contains_any(
        title_summary,
        central_bank_policy_indicators,
    )

    has_company = _contains_any(
        title_summary,
        company_indicators,
    )

    has_explicit_market = _contains_any(
        title_summary,
        explicit_market_indicators,
    )

    # ------------------------------------------------------------------
    # 5. Category determination
    # ------------------------------------------------------------------

    if is_crypto:
        category = "crypto"

    elif has_central_bank_policy:
        # Central-bank articles need one additional distinction.
        #
        # Example:
        #   "BoE's Lombardelli says rates may stay high"
        #       -> policy
        #
        #   "RBI inflation outlook remains challenging"
        #       -> macro
        #
        central_bank_macro_indicators = (
            "inflation",
            "gdp",
            "unemployment",
            "nonfarm payroll",
            "cpi",
            "ppi",
            "bond yield",
            "bond yields",
            "bond market",
            "bond markets",
            "economic growth",
            "economic data",
        )

        if _contains_any(
                title_text,
                central_bank_macro_indicators,
        ):
            category = "macro"
        else:
            category = "policy"

    elif has_policy:
        category = "policy"

    elif has_explicit_market:
        category = "market"

    elif has_strong_macro:
        category = "macro"

    elif has_company:
        category = "company"

    else:
        category = "general"

    # ------------------------------------------------------------------
    # 6. Asset-class indicators
    # ------------------------------------------------------------------

    index_indicators = (
        "nifty",
        "nifty 50",
        "nifty50",
        "bank nifty",
        "sensex",
        "nasdaq",
        "s&p 500",
        "dow jones",
        "nikkei",
        "hang seng",
        "index",
        "indices",
        "benchmark",
        "benchmarks",
    )

    equity_indicators = (
        "stock",
        "stocks",
        "share",
        "shares",
        "equity",
        "equities",
        "earnings",
        "profit",
        "profits",
        "revenue",
        "guidance",
        "merger",
        "mergers",
        "acquisition",
        "acquisitions",
        "ipo",
        "fundraise",
        "fundraising",
        "stake sale",
        "market share",
        "contract",
        "order win",
        "wins contract",
        "launch",
        "launches",
        "partnership",
        "deal",
        "seasonal jobs",
        "dividend",
        "dividends",
        "capex",
        "joint venture",
    )

    # ------------------------------------------------------------------
    # 7. Asset-class determination
    # ------------------------------------------------------------------

    if is_crypto:
        asset_class = "crypto"

    elif category == "macro":
        asset_class = "macro"

    elif category == "market":

        if _contains_any(
                title_summary,
                index_indicators,
        ):
            asset_class = "index"

        elif _contains_any(
                title_summary,
                equity_indicators,
        ):
            asset_class = "equity"

        else:
            asset_class = "unknown"

    elif _contains_any(
            title_summary,
            equity_indicators,
    ):
        asset_class = "equity"

    else:
        asset_class = "unknown"

    # ------------------------------------------------------------------
    # 8. Return classification
    # ------------------------------------------------------------------

    return NewsClassification(
        market=market,
        geography=geography,
        asset_class=asset_class,
        category=category,
    )