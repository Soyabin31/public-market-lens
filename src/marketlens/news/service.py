from __future__ import annotations

from pathlib import Path

import pandas as pd

from marketlens.news.repository import read_articles


def get_latest_news(
        limit: int = 25,
        market: str | None = None,
        symbol: str | None = None,
        db_path: Path | None = None,
) -> pd.DataFrame:
    """
    Return the newest persisted news articles for UI consumption.

    The service layer keeps UI code independent from the repository's
    database query implementation.
    """
    if limit <= 0:
        raise ValueError(
            "limit must be greater than zero."
        )

    articles = read_articles(
        market=market,
        symbol=symbol,
        limit=limit,
        db_path=db_path,
    )

    if articles.empty:
        return articles

    ui_columns = [
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

    return articles.loc[:, ui_columns].copy()