from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from marketlens.news.ingestion import _classify_articles
from marketlens.db import connect, initialize_schema

from marketlens.db import initialize_database
from marketlens.news.models import NewsArticle
from marketlens.news.normalize import (
    build_article_identity,
    build_content_hash,
    canonicalize_url,
    normalize_text,
)
from marketlens.news.repository import (
    read_articles,
    upsert_articles,
)


@pytest.fixture
def initialized_db(tmp_path):
    """
    Create a temporary DuckDB database with the full
    Market Lens schema initialized.
    """
    db_path = tmp_path / "news.duckdb"

    initialize_database(
        db_path=db_path,
    )

    return db_path


def make_article(
        title: str = "Test article",
        summary: str = "Test summary",
) -> NewsArticle:
    now = datetime(
        2026,
        9,
        18,
        10,
        30,
        tzinfo=timezone.utc,
    )

    canonical_url = canonicalize_url(
        "https://example.com/article/123"
        "?utm_source=rss"
    )

    content_hash = build_content_hash(
        title,
        summary,
    )

    return NewsArticle(
        source="Example News",
        source_type="RSS",
        url=(
            "https://example.com/article/123"
            "?utm_source=rss"
        ),
        canonical_url=canonical_url,
        title=normalize_text(title),
        summary=normalize_text(summary),
        body="Full test article body.",
        published_at=now,
        ingested_at=now,
        content_hash=content_hash,
        language="en",
        author="Test Author",
        market="us",
        symbol="AAPL",
        raw_metadata=json.dumps(
            {"test": True}
        ),
    )


def test_normalize_text():
    assert normalize_text(
        "  Hello    world \n test  "
    ) == "Hello world test"


def test_canonicalize_url_removes_tracking_parameters():
    url = (
        "https://Example.com/article/123"
        "?utm_source=rss"
        "&utm_medium=email"
        "&page=2"
    )

    assert canonicalize_url(url) == (
        "https://example.com/article/123?page=2"
    )


def test_content_hash_is_deterministic():
    first = build_content_hash(
        "Title",
        "Summary",
    )

    second = build_content_hash(
        "Title",
        "Summary",
    )

    assert first == second


def test_content_hash_changes_when_content_changes():
    first = build_content_hash(
        "Title",
        "Summary",
    )

    second = build_content_hash(
        "Title changed",
        "Summary",
    )

    assert first != second


def test_article_id_is_deterministic():
    article = make_article()

    expected = build_article_identity(
        article.canonical_url,
        article.content_hash,
    )

    assert article.article_id == expected


def test_upsert_articles_is_idempotent(
        initialized_db,
):
    db_path = initialized_db

    article = make_article()

    inserted_first = upsert_articles(
        [article],
        db_path=db_path,
    )

    inserted_second = upsert_articles(
        [article],
        db_path=db_path,
    )

    assert inserted_first == 1
    assert inserted_second == 1

    stored = read_articles(
        db_path=db_path,
    )

    assert len(stored) == 1
    assert (
            stored.iloc[0]["article_id"]
            == article.article_id
    )


def test_read_articles_filters_by_market_and_symbol(
        initialized_db,
):
    db_path = initialized_db

    us_article = make_article()

    india_article = NewsArticle(
        source="Example India",
        source_type="RSS",
        url="https://example.com/india/1",
        canonical_url="https://example.com/india/1",
        title="India article",
        summary="India summary",
        body="India article body.",
        published_at=us_article.published_at,
        ingested_at=us_article.ingested_at,
        content_hash=build_content_hash(
            "India article",
            "India summary",
        ),
        market="india",
        symbol="RELIANCE.NS",
    )

    upsert_articles(
        [us_article, india_article],
        db_path=db_path,
    )

    result = read_articles(
        market="india",
        symbol="RELIANCE.NS",
        db_path=db_path,
    )

    assert len(result) == 1
    assert (
            result.iloc[0]["symbol"]
            == "RELIANCE.NS"
    )


def test_empty_upsert_does_nothing(
        initialized_db,
):
    db_path = initialized_db

    assert upsert_articles(
        [],
        db_path=db_path,
    ) == 0

    result = read_articles(
        db_path=db_path,
    )

    assert result.empty


def test_invalid_url_is_rejected():
    with pytest.raises(ValueError):
        canonicalize_url(
            "not-a-valid-url"
        )


def test_classification_survives_news_persistence(tmp_path):
    db_path = tmp_path / "news_integration.duckdb"

    with connect(db_path) as connection:
        initialize_schema(connection)

    article = NewsArticle(
        source="Test Source",
        source_type="RSS",
        url="https://example.com/us-economy",
        canonical_url="https://example.com/us-economy",
        title="US economy firming as inflation risks persist",
        summary="The Federal Reserve is monitoring inflation and economic growth.",
        published_at=datetime.now(timezone.utc),
        ingested_at=datetime.now(timezone.utc),
        content_hash="integration-test-us-macro",
    )

    classified_articles = _classify_articles(
        [article]
    )

    classified_article = classified_articles[0]

    assert classified_article.market == "us"
    assert classified_article.geography == "US"
    assert classified_article.asset_class == "macro"
    assert classified_article.category == "macro"

    upsert_articles(
        articles=classified_articles,
        db_path=db_path,
    )

    stored_articles = read_articles(
        db_path=db_path,
    )

    assert len(stored_articles) == 1

    stored_article = stored_articles.iloc[0]

    assert stored_article["market"] == "us"
    assert stored_article["geography"] == "US"
    assert stored_article["asset_class"] == "macro"
    assert stored_article["category"] == "macro"