from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from marketlens.db import connect
from marketlens.news.models import NewsArticle


def upsert_articles(
        articles: list[NewsArticle],
        db_path: Path | None = None,
) -> int:
    """
    Insert normalized articles into DuckDB.

    Repeated ingestion is safe because article_id is stable.

    Existing articles are updated rather than duplicated.
    """
    if not articles:
        return 0

    rows = pd.DataFrame(
        [
            {
                "article_id": article.article_id,
                "source": article.source,
                "source_type": article.source_type,
                "url": article.url,
                "canonical_url": article.canonical_url,
                "title": article.title,
                "summary": article.summary,
                "published_at": article.published_at,
                "ingested_at": article.ingested_at,
                "content_hash": article.content_hash,
                "language": article.language,
                "author": article.author,
                "market": article.market,
                "symbol": article.symbol,
                "geography": article.geography,
                "asset_class": article.asset_class,
                "category": article.category,
                "raw_metadata": article.raw_metadata,
            }
            for article in articles
        ]
    )

    with connect(db_path) as connection:
        connection.register(
            "news_articles",
            rows,
        )

        connection.execute(
            """
            INSERT INTO articles (
                article_id,
                source,
                source_type,
                url,
                canonical_url,
                title,
                summary,
                published_at,
                ingested_at,
                content_hash,
                language,
                author,
                market,
                symbol,
                geography,
                asset_class,
                category,
                raw_metadata
            )
            SELECT
                article_id,
                source,
                source_type,
                url,
                canonical_url,
                title,
                summary,
                published_at,
                ingested_at,
                content_hash,
                language,
                author,
                market,
                symbol,
                geography,
                asset_class,
                category,
                raw_metadata
            FROM news_articles
            ON CONFLICT (article_id)
                DO UPDATE SET
                source = EXCLUDED.source,
                       source_type = EXCLUDED.source_type,
                       url = EXCLUDED.url,
                       canonical_url = EXCLUDED.canonical_url,
                       title = EXCLUDED.title,
                       summary = EXCLUDED.summary,
                       published_at = EXCLUDED.published_at,
                       ingested_at = EXCLUDED.ingested_at,
                       content_hash = EXCLUDED.content_hash,
                       language = EXCLUDED.language,
                       author = EXCLUDED.author,
                       market = EXCLUDED.market,
                       symbol = EXCLUDED.symbol,
                       geography = EXCLUDED.geography,
                       asset_class = EXCLUDED.asset_class,
                       category = EXCLUDED.category,
                       raw_metadata = EXCLUDED.raw_metadata
            """
        )

    return len(rows)


def count_existing_articles(
        articles: list[NewsArticle],
        db_path: Path | None = None,
) -> int:
    """
    Count how many supplied articles already exist in the database.

    Article identity is based on article_id, which is derived from
    canonical URL and content hash.
    """
    if not articles:
        return 0

    article_ids = [
        article.article_id
        for article in articles
    ]

    placeholders = ", ".join(
        "?"
        for _ in article_ids
    )

    query = f"""
        SELECT COUNT(*)
        FROM articles
        WHERE article_id IN ({placeholders})
    """

    with connect(db_path) as connection:
        return connection.execute(
            query,
            article_ids,
        ).fetchone()[0]


def read_articles(
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        market: str | None = None,
        symbol: str | None = None,
        limit: int | None = None,
        db_path: Path | None = None,
) -> pd.DataFrame:
    """
    Read persisted news articles using optional filters.

    Results are returned newest first.

    If limit is provided, only the newest matching articles
    up to that limit are returned.
    """
    if limit is not None and limit <= 0:
        raise ValueError(
            "limit must be greater than zero."
        )

    conditions: list[str] = []
    parameters: list[object] = []

    if start_time is not None:
        conditions.append(
            "published_at >= ?"
        )
        parameters.append(start_time)

    if end_time is not None:
        conditions.append(
            "published_at < ?"
        )
        parameters.append(end_time)

    if market is not None:
        conditions.append(
            "market = ?"
        )
        parameters.append(market)

    if symbol is not None:
        conditions.append(
            "symbol = ?"
        )
        parameters.append(symbol)

    where_clause = ""

    if conditions:
        where_clause = (
                "WHERE "
                + " AND ".join(conditions)
        )

    limit_clause = ""

    if limit is not None:
        limit_clause = "LIMIT ?"
        parameters.append(limit)

    query = f"""
        SELECT
            article_id,
            source,
            source_type,
            url,
            canonical_url,
            title,
            summary,
            published_at,
            ingested_at,
            content_hash,
            language,
            author,
            market,
            symbol,
            geography,
            asset_class,
            category,
            raw_metadata
        FROM articles
        {where_clause}
        ORDER BY published_at DESC, article_id ASC
        {limit_clause}
    """

    with connect(db_path) as connection:
        return connection.execute(
            query,
            parameters,
        ).df()