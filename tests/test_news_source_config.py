from __future__ import annotations

from pathlib import Path

from marketlens.news.source_config import (
    enabled_news_sources,
    load_news_sources,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_news_source_configuration_loads():
    sources = load_news_sources()

    assert sources

    source_ids = {
        source.id
        for source in sources
    }

    assert "economic_times_markets" in source_ids
    assert "business_standard_markets" in source_ids
    assert "mint_markets" in source_ids
    assert "reuters_markets" in source_ids
    assert "rbi_press_releases" in source_ids


def test_news_source_configuration_has_unique_ids():
    sources = load_news_sources()

    source_ids = [
        source.id
        for source in sources
    ]

    assert len(source_ids) == len(set(source_ids))


def test_enabled_sources_have_feed_urls():
    sources = enabled_news_sources()

    assert sources

    for source in sources:
        assert source.feed_url
        assert source.feed_url.startswith(
            ("http://", "https://")
        )


def test_disabled_sources_are_not_returned_as_enabled():
    sources = enabled_news_sources()

    source_ids = {
        source.id
        for source in sources
    }

    assert "reuters_markets" not in source_ids
    assert "bloomberg_markets" not in source_ids
    assert "cnbc_markets" not in source_ids


def test_source_categories_are_immutable_tuples():
    sources = load_news_sources()

    for source in sources:
        assert isinstance(
            source.categories,
            tuple,
        )