from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class NewsSourceConfig:
    """
    Configuration for one news source/feed.
    """

    id: str
    name: str
    publisher: str
    source_type: str
    tier: int
    market: str
    enabled: bool
    feed_url: str
    categories: tuple[str, ...]
    timeout_seconds: int
    max_articles_per_feed: int


def load_news_sources(
        config_path: Path | None = None,
) -> list[NewsSourceConfig]:
    """
    Load enabled/disabled news source definitions
    from config/news_sources.yaml.
    """

    if config_path is None:
        config_path = (
                Path(__file__).resolve().parents[3]
                / "config"
                / "news_sources.yaml"
        )

    with config_path.open(
            "r",
            encoding="utf-8",
    ) as file:
        configuration = yaml.safe_load(file)

    if not isinstance(configuration, dict):
        raise ValueError(
            "News source configuration must be a YAML mapping."
        )

    defaults = configuration.get(
        "defaults",
        {},
    )

    sources = configuration.get(
        "sources",
        [],
    )

    if not isinstance(sources, list):
        raise ValueError(
            "'sources' must be a YAML list."
        )

    result: list[NewsSourceConfig] = []

    for source in sources:
        if not isinstance(source, dict):
            raise ValueError(
                "Each news source must be a YAML mapping."
            )

        timeout_seconds = int(
            source.get(
                "timeout_seconds",
                defaults.get(
                    "timeout_seconds",
                    20,
                ),
            )
        )

        max_articles_per_feed = int(
            source.get(
                "max_articles_per_feed",
                defaults.get(
                    "max_articles_per_feed",
                    100,
                ),
            )
        )

        categories = source.get(
            "categories",
            [],
        )

        if not isinstance(categories, list):
            raise ValueError(
                f"Categories must be a list: "
                f"{source.get('id')}"
            )

        result.append(
            NewsSourceConfig(
                id=str(source["id"]),
                name=str(source["name"]),
                publisher=str(source["publisher"]),
                source_type=str(
                    source.get(
                        "source_type",
                        defaults.get(
                            "source_type",
                            "publisher",
                        ),
                    )
                ),
                tier=int(source["tier"]),
                market=str(source["market"]),
                enabled=bool(
                    source.get(
                        "enabled",
                        defaults.get(
                            "enabled",
                            True,
                        ),
                    )
                ),
                feed_url=str(
                    source.get(
                        "feed_url",
                        "",
                    )
                ),
                categories=tuple(
                    str(category)
                    for category in categories
                ),
                timeout_seconds=timeout_seconds,
                max_articles_per_feed=max_articles_per_feed,
            )
        )

    return result


def enabled_news_sources(
        config_path: Path | None = None,
) -> list[NewsSourceConfig]:
    """
    Return only sources that are explicitly enabled
    and have a feed URL.
    """

    sources = load_news_sources(
        config_path=config_path,
    )

    return [
        source
        for source in sources
        if source.enabled
           and bool(source.feed_url.strip())
    ]