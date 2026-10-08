from __future__ import annotations

from datetime import datetime, timezone

import articles
import pytest

from marketlens.db import initialize_database
from marketlens.news.models import NewsArticle
from marketlens.news.repository import (
    count_existing_articles,
    upsert_articles, read_articles,
)


def _article(
        identifier: str,
        published_at: datetime | None = None,
) -> NewsArticle:
    if published_at is None:
        published_at = datetime(
            2026,
            9,
            22,
            10,
            0,
            tzinfo=timezone.utc,
        )

    return NewsArticle(
        source="Test Source",
        source_type="publisher",
        url=f"https://example.com/{identifier}",
        canonical_url=f"https://example.com/{identifier}",
        title=f"Test Article {identifier}",
        summary="Test summary",
        published_at=published_at,
        ingested_at=published_at,
        content_hash=f"hash-{identifier}",
    )


def test_count_existing_articles_returns_zero_for_new_articles(
        tmp_path,
) -> None:
    db_path = tmp_path / "test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    articles = [
        _article("one"),
        _article("two"),
    ]

    assert (
            count_existing_articles(
                articles=articles,
                db_path=db_path,
            )
            == 0
    )


def test_count_existing_articles_counts_persisted_articles(
        tmp_path,
) -> None:
    db_path = tmp_path / "test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    articles = [
        _article("one"),
        _article("two"),
    ]

    upsert_articles(
        articles=[articles[0]],
        db_path=db_path,
    )

    assert (
            count_existing_articles(
                articles=articles,
                db_path=db_path,
            )
            == 1
    )


def test_upsert_is_idempotent_for_same_articles(
        tmp_path,
) -> None:
    db_path = tmp_path / "test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    articles = [
        _article("one"),
        _article("two"),
    ]

    first_count = upsert_articles(
        articles=articles,
        db_path=db_path,
    )

    existing_after_first = count_existing_articles(
        articles=articles,
        db_path=db_path,
    )

    second_count = upsert_articles(
        articles=articles,
        db_path=db_path,
    )

    existing_after_second = count_existing_articles(
        articles=articles,
        db_path=db_path,
    )

    assert first_count == 2
    assert existing_after_first == 2

    assert second_count == 2
    assert existing_after_second == 2

def test_read_articles_returns_articles_newest_first(
        tmp_path,
) -> None:
    db_path = tmp_path / "read_articles_order_test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    first_published_at = datetime(
        2026,
        9,
        23,
        9,
        0,
        tzinfo=timezone.utc,
    )

    second_published_at = datetime(
        2026,
        9,
        23,
        10,
        0,
        tzinfo=timezone.utc,
    )

    first_article = _article(
        identifier="read-order-first",
        published_at=first_published_at,
    )

    second_article = _article(
        identifier="read-order-second",
        published_at=second_published_at,
    )

    upsert_articles(
        articles=[
            first_article,
            second_article,
        ],
        db_path=db_path,
    )

    result = read_articles(
        db_path=db_path,
    )

    assert len(result) == 2

    assert result.iloc[0]["article_id"] == (
        second_article.article_id
    )

    assert result.iloc[1]["article_id"] == (
        first_article.article_id
    )

    assert result.iloc[0]["published_at"] >= (
        result.iloc[1]["published_at"]
    )

def test_read_articles_filters_by_time_window(
        tmp_path,
) -> None:
    db_path = tmp_path / "read_articles_time_filter_test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    first_published_at = datetime(
        2026,
        9,
        23,
        9,
        0,
        tzinfo=timezone.utc,
    )

    second_published_at = datetime(
        2026,
        9,
        23,
        10,
        0,
        tzinfo=timezone.utc,
    )

    third_published_at = datetime(
        2026,
        9,
        23,
        11,
        0,
        tzinfo=timezone.utc,
    )

    first_article = _article(
        identifier="time-filter-first",
        published_at=first_published_at,
    )

    second_article = _article(
        identifier="time-filter-second",
        published_at=second_published_at,
    )

    third_article = _article(
        identifier="time-filter-third",
        published_at=third_published_at,
    )

    test_articles = [
        first_article,
        second_article,
        third_article,
    ]

    upsert_articles(
        articles=test_articles,
        db_path=db_path,
    )

    result = read_articles(
        start_time=second_published_at,
        end_time=third_published_at,
        db_path=db_path,
    )

    assert len(result) == 1

    assert result.iloc[0]["article_id"] == (
        second_article.article_id
    )


def test_read_articles_filters_by_market_and_symbol(
        tmp_path,
) -> None:
    db_path = tmp_path / "read_articles_market_symbol_test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    india_article = NewsArticle(
        source="Test Source",
        source_type="publisher",
        url="https://example.com/market-india",
        canonical_url="https://example.com/market-india",
        title="India Market Article",
        summary="India market test",
        published_at=datetime(
            2026,
            9,
            23,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        ingested_at=datetime(
            2026,
            9,
            23,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        content_hash="hash-market-india",
        market="IN",
        symbol="RELIANCE",
    )

    us_article = NewsArticle(
        source="Test Source",
        source_type="publisher",
        url="https://example.com/market-us",
        canonical_url="https://example.com/market-us",
        title="US Market Article",
        summary="US market test",
        published_at=datetime(
            2026,
            9,
            23,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        ingested_at=datetime(
            2026,
            9,
            23,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        content_hash="hash-market-us",
        market="US",
        symbol="AAPL",
    )

    test_articles = [
        india_article,
        us_article,
    ]

    upsert_articles(
        articles=test_articles,
        db_path=db_path,
    )

    india_result = read_articles(
        market="IN",
        db_path=db_path,
    )

    assert len(india_result) == 1
    assert india_result.iloc[0]["article_id"] == (
        india_article.article_id
    )
    assert india_result.iloc[0]["symbol"] == "RELIANCE"

    us_symbol_result = read_articles(
        market="US",
        symbol="AAPL",
        db_path=db_path,
    )

    assert len(us_symbol_result) == 1
    assert us_symbol_result.iloc[0]["article_id"] == (
        us_article.article_id
    )
    assert us_symbol_result.iloc[0]["market"] == "US"


def test_read_articles_applies_limit(
        tmp_path,
) -> None:
    db_path = tmp_path / "read_articles_limit_test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    first_article = _article(
        identifier="limit-first",
        published_at=datetime(
            2026,
            9,
            23,
            9,
            0,
            tzinfo=timezone.utc,
        ),
    )

    second_article = _article(
        identifier="limit-second",
        published_at=datetime(
            2026,
            9,
            23,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    third_article = _article(
        identifier="limit-third",
        published_at=datetime(
            2026,
            9,
            23,
            11,
            0,
            tzinfo=timezone.utc,
        ),
    )

    upsert_articles(
        articles=[
            first_article,
            second_article,
            third_article,
        ],
        db_path=db_path,
    )

    result = read_articles(
        limit=2,
        db_path=db_path,
    )

    assert len(result) == 2

    assert result.iloc[0]["article_id"] == (
        third_article.article_id
    )

    assert result.iloc[1]["article_id"] == (
        second_article.article_id
    )


def test_read_articles_rejects_non_positive_limit(
        tmp_path,
) -> None:
    db_path = tmp_path / "read_articles_invalid_limit_test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    with pytest.raises(
            ValueError,
            match="limit must be greater than zero.",
    ):
        read_articles(
            limit=0,
            db_path=db_path,
        )

    with pytest.raises(
            ValueError,
            match="limit must be greater than zero.",
    ):
        read_articles(
            limit=-1,
            db_path=db_path,
        )

