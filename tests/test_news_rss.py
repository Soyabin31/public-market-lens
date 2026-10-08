from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from marketlens.news.rss import (
    _build_article,
    _parse_entry_datetime,
)
from marketlens.news.source_config import (
    NewsSourceConfig,
)


def make_source(
        feed_url: str = "https://example.com/feed.xml",
) -> NewsSourceConfig:
    return NewsSourceConfig(
        id="test_source",
        name="Test News",
        publisher="Test Publisher",
        source_type="publisher",
        tier=1,
        market="us",
        enabled=True,
        feed_url=feed_url,
        categories=("markets",),
        timeout_seconds=10,
        max_articles_per_feed=100,
    )


def test_parse_entry_datetime_from_parsed_timestamp():
    entry = {
        "published_parsed": (
            2026,
            9,
            22,
            10,
            30,
            0,
            1,
            265,
            0,
        )
    }

    result = _parse_entry_datetime(
        entry
    )

    assert result is not None
    assert result.tzinfo == timezone.utc
    assert result.year == 2026
    assert result.month == 9
    assert result.day == 22


def test_parse_entry_datetime_from_string():
    entry = {
        "published": (
            "Tue, 22 Sep 2026 10:30:00 GMT"
        )
    }

    result = _parse_entry_datetime(
        entry
    )

    assert result is not None
    assert result.tzinfo == timezone.utc
    assert result.hour == 10
    assert result.minute == 30


def test_build_article_normalizes_feed_entry():
    entry = SimpleNamespace(
        title="  Market   Rally  ",
        link=(
            "https://example.com/article/1"
            "?utm_source=rss"
        ),
        summary=(
            "  Stocks rise strongly.  "
        ),
        published_parsed=(
            2026,
            9,
            22,
            10,
            30,
            0,
            1,
            265,
            0,
        ),
        author="Test Author",
    )

    # feedparser entries behave like dictionaries,
    # so use a normal mapping for the actual test.
    entry = {
        "title": entry.title,
        "link": entry.link,
        "summary": entry.summary,
        "published_parsed": (
            2026,
            9,
            22,
            10,
            30,
            0,
            1,
            265,
            0,
        ),
        "author": entry.author,
    }

    article = _build_article(
        entry=entry,
        source=make_source(),
        fetched_at=datetime(
            2026,
            9,
            22,
            11,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert article is not None
    assert article.title == "Market Rally"
    assert article.summary == "Stocks rise strongly."
    assert article.author == "Test Author"
    assert (
            article.canonical_url
            == "https://example.com/article/1"
    )
    assert article.market == "us"
    assert article.body is None


def test_build_article_rejects_missing_title():
    entry = {
        "link": "https://example.com/article/1",
        "summary": "Summary",
        "published_parsed": (
            2026,
            9,
            22,
            10,
            30,
            0,
            1,
            265,
            0,
        ),
    }

    article = _build_article(
        entry=entry,
        source=make_source(),
        fetched_at=datetime.now(
            timezone.utc
        ),
    )

    assert article is None


def test_build_article_rejects_missing_url():
    entry = {
        "title": "Test title",
        "summary": "Summary",
        "published_parsed": (
            2026,
            9,
            22,
            10,
            30,
            0,
            1,
            265,
            0,
        ),
    }

    article = _build_article(
        entry=entry,
        source=make_source(),
        fetched_at=datetime.now(
            timezone.utc
        ),
    )

    assert article is None


def test_build_article_rejects_missing_publication_time():
    entry = {
        "title": "Test title",
        "link": "https://example.com/article/1",
        "summary": "Summary",
    }

    article = _build_article(
        entry=entry,
        source=make_source(),
        fetched_at=datetime.now(
            timezone.utc
        ),
    )

    assert article is None