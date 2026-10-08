from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from marketlens.db import write_run_log
from marketlens.news.models import NewsArticle
from marketlens.news.classifier import classify_article
from marketlens.news.repository import (
    count_existing_articles,
    upsert_articles,
)
from marketlens.news.rss import FeedFetchResult, fetch_feed
from marketlens.news.source_config import enabled_news_sources


@dataclass(frozen=True)
class SourceIngestionResult:
    """
    Result of ingesting one configured news source.
    """

    source_id: str
    source_name: str
    status: str
    http_status: int | None
    fetched_articles: int
    unique_articles: int
    error_message: str | None


@dataclass(frozen=True)
class NewsIngestionResult:
    """
    Result of one complete news-ingestion run.
    """

    started_at: datetime
    completed_at: datetime

    window_start: datetime
    window_end: datetime

    sources_attempted: int
    sources_healthy: int
    sources_empty: int
    sources_failed: int

    articles_fetched: int
    articles_unique: int
    articles_existing: int
    articles_inserted: int

    source_results: tuple[SourceIngestionResult, ...]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_aware_utc(value: datetime) -> datetime:
    """
    Normalize a datetime to timezone-aware UTC.

    The ingestion layer uses UTC internally so that source timestamps
    from India, US, and future global markets can be compared safely.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _article_in_window(
        article: NewsArticle,
        window_start: datetime,
        window_end: datetime,
) -> bool:
    published_at = _make_aware_utc(article.published_at)

    return (
            published_at >= window_start
            and published_at < window_end
    )

def _classify_articles(
        articles: list[NewsArticle],
) -> list[NewsArticle]:
    """
    Apply deterministic classification to every normalized article.

    Classification is performed before deduplication and persistence
    so that geography, asset class, and category are stored alongside
    the article itself.
    """
    classified_articles: list[NewsArticle] = []

    for article in articles:
        classification = classify_article(
            source=article.source,
            url=article.url,
            title=article.title,
            summary=article.summary,
        )

        classified_article = replace(
            article,
            market=classification.market,
            geography=classification.geography,
            asset_class=classification.asset_class,
            category=classification.category,
        )

        classified_articles.append(
            classified_article
        )

    return classified_articles

def _deduplicate_articles(
        articles: list[NewsArticle],
) -> list[NewsArticle]:
    """
    Deduplicate articles using the stable article_id.

    The same story may appear in multiple feeds. We retain the first
    occurrence within this ingestion run.
    """
    unique_articles: list[NewsArticle] = []
    seen_article_ids: set[str] = set()

    for article in articles:
        if article.article_id in seen_article_ids:
            continue

        seen_article_ids.add(article.article_id)
        unique_articles.append(article)

    return unique_articles


def _filter_articles_to_window(
        articles: list[NewsArticle],
        window_start: datetime,
        window_end: datetime,
) -> list[NewsArticle]:
    return [
        article
        for article in articles
        if _article_in_window(
            article=article,
            window_start=window_start,
            window_end=window_end,
        )
    ]


def _convert_feed_result(
        result: FeedFetchResult,
        window_start: datetime,
        window_end: datetime,
) -> tuple[SourceIngestionResult, list[NewsArticle]]:
    articles = _filter_articles_to_window(
        articles=list(result.articles),
        window_start=window_start,
        window_end=window_end,
    )

    source_result = SourceIngestionResult(
        source_id=result.source_id,
        source_name=result.source_name,
        status=result.status,
        http_status=result.http_status,
        fetched_articles=result.article_count,
        unique_articles=len(articles),
        error_message=result.error_message,
    )

    return source_result, articles


def ingest_news(
        catch_up_hours: int = 72,
        db_path: Path | None = None,
) -> NewsIngestionResult:
    """
    Execute one complete news-ingestion run.

    The default window is the previous 72 hours up to the current UTC
    time. This allows a run to recover articles after the application
    or scheduler has been offline.

    Persistence is idempotent because article identity is based on
    the normalized article URL and content hash.
    """
    started_at = _utc_now()

    if catch_up_hours <= 0:
        raise ValueError(
            "catch_up_hours must be greater than zero."
        )

    window_end = started_at
    window_start = window_end - timedelta(
        hours=catch_up_hours
    )

    sources = enabled_news_sources()

    source_results: list[SourceIngestionResult] = []
    all_articles: list[NewsArticle] = []

    try:
        for source in sources:
            feed_result = fetch_feed(source)

            source_result, articles = _convert_feed_result(
                result=feed_result,
                window_start=window_start,
                window_end=window_end,
            )

            source_results.append(source_result)
            all_articles.extend(articles)

            classified_articles = _classify_articles(
                all_articles
            )

            unique_articles = _deduplicate_articles(
                classified_articles
            )

        existing_articles = count_existing_articles(
            articles=unique_articles,
            db_path=db_path,
        )

        upsert_articles(
            articles=unique_articles,
            db_path=db_path,
        )

        inserted_articles = (
                len(unique_articles)
                - existing_articles
        )

        completed_at = _utc_now()

        write_run_log(
            stage="NEWS_INGESTION",
            status="SUCCESS",
            rows=inserted_articles,
            detail=(
                f"fetched={len(all_articles)}; "
                f"unique={len(unique_articles)}; "
                f"existing={existing_articles}; "
                f"inserted={inserted_articles}; "
                f"sources={len(sources)}"
            ),
            run_at=completed_at,
            db_path=db_path,
        )

    except Exception as exc:
        failed_at = _utc_now()

        try:
            write_run_log(
                stage="NEWS_INGESTION",
                status="FAILED",
                rows=0,
                detail=(
                    f"error={type(exc).__name__}: {exc}"
                ),
                run_at=failed_at,
                db_path=db_path,
            )
        except Exception:
            pass

        raise

    healthy_count = sum(
        1
        for result in source_results
        if result.status == "HEALTHY"
    )

    empty_count = sum(
        1
        for result in source_results
        if result.status == "EMPTY"
    )

    failed_count = sum(
        1
        for result in source_results
        if result.status == "FAILED"
    )

    return NewsIngestionResult(
        started_at=started_at,
        completed_at=completed_at,
        window_start=window_start,
        window_end=window_end,
        sources_attempted=len(sources),
        sources_healthy=healthy_count,
        sources_empty=empty_count,
        sources_failed=failed_count,
        articles_fetched=len(all_articles),
        articles_unique=len(unique_articles),
        articles_existing=existing_articles,
        articles_inserted=inserted_articles,
        source_results=tuple(source_results),
    )