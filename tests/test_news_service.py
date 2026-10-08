from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from marketlens.db import initialize_database
from marketlens.news.models import NewsArticle
from marketlens.news.repository import upsert_articles
from marketlens.news.service import get_latest_news


def _article(
        identifier: str,
        published_at: datetime,
        market: str | None = None,
        symbol: str | None = None,
) -> NewsArticle:
    return NewsArticle(
        source="Test Source",
        source_type="publisher",
        url=f"https://example.com/{identifier}",
        canonical_url=f"https://example.com/{identifier}",
        title=f"Test Article {identifier}",
        summary=f"Summary for {identifier}",
        published_at=published_at,
        ingested_at=published_at,
        content_hash=f"hash-{identifier}",
        market=market,
        symbol=symbol,
    )


def test_get_latest_news_returns_newest_articles(
        tmp_path,
) -> None:
    db_path = tmp_path / "service.duckdb"

    initialize_database(db_path)

    now = datetime.now(timezone.utc)

    articles = [
        _article(
            identifier="old",
            published_at=now - timedelta(hours=3),
        ),
        _article(
            identifier="middle",
            published_at=now - timedelta(hours=2),
        ),
        _article(
            identifier="new",
            published_at=now - timedelta(hours=1),
        ),
    ]

    upsert_articles(
        articles=articles,
        db_path=db_path,
    )

    result = get_latest_news(
        limit=2,
        db_path=db_path,
    )

    assert len(result) == 2
    assert list(result["title"]) == [
        "Test Article new",
        "Test Article middle",
    ]


def test_get_latest_news_returns_only_ui_columns(
        tmp_path,
) -> None:
    db_path = tmp_path / "service_columns.duckdb"

    initialize_database(db_path)

    published_at = datetime.now(timezone.utc)

    upsert_articles(
        articles=[
            _article(
                identifier="one",
                published_at=published_at,
            )
        ],
        db_path=db_path,
    )

    result = get_latest_news(
        limit=10,
        db_path=db_path,
    )

    expected_columns = [
        "article_id",
        "source",
        "source_type",
        "url",
        "title",
        "summary",
        "published_at",
        "market",
        "symbol",
    ]

    assert list(result.columns) == expected_columns


def test_get_latest_news_filters_by_market(
        tmp_path,
) -> None:
    db_path = tmp_path / "service_market.duckdb"

    initialize_database(db_path)

    now = datetime.now(timezone.utc)

    upsert_articles(
        articles=[
            _article(
                identifier="india",
                published_at=now,
                market="INDIA",
            ),
            _article(
                identifier="us",
                published_at=now - timedelta(minutes=1),
                market="US",
            ),
        ],
        db_path=db_path,
    )

    result = get_latest_news(
        limit=10,
        market="INDIA",
        db_path=db_path,
    )

    assert len(result) == 1
    assert result.iloc[0]["title"] == "Test Article india"


def test_get_latest_news_filters_by_symbol(
        tmp_path,
) -> None:
    db_path = tmp_path / "service_symbol.duckdb"

    initialize_database(db_path)

    now = datetime.now(timezone.utc)

    upsert_articles(
        articles=[
            _article(
                identifier="reliance",
                published_at=now,
                symbol="RELIANCE",
            ),
            _article(
                identifier="tcs",
                published_at=now - timedelta(minutes=1),
                symbol="TCS",
            ),
        ],
        db_path=db_path,
    )

    result = get_latest_news(
        limit=10,
        symbol="RELIANCE",
        db_path=db_path,
    )

    assert len(result) == 1
    assert result.iloc[0]["title"] == "Test Article reliance"


def test_get_latest_news_rejects_invalid_limit(
        tmp_path,
) -> None:
    db_path = tmp_path / "service_invalid_limit.duckdb"

    initialize_database(db_path)

    with pytest.raises(
            ValueError,
            match="limit must be greater than zero",
    ):
        get_latest_news(
            limit=0,
            db_path=db_path,
        )


def test_get_latest_news_returns_empty_dataframe(
        tmp_path,
) -> None:
    db_path = tmp_path / "service_empty.duckdb"

    initialize_database(db_path)

    result = get_latest_news(
        limit=10,
        db_path=db_path,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.empty