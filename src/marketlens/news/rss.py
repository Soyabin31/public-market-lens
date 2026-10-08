from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import feedparser

from marketlens.news.models import NewsArticle
from marketlens.news.normalize import (
    build_content_hash,
    canonicalize_url,
    normalize_text,
)
from marketlens.news.source_config import NewsSourceConfig


USER_AGENT = (
    "MarketLens/0.1 "
    "(financial-market-research; "
    "contact=local-development)"
)


@dataclass(frozen=True)
class FeedFetchResult:
    """
    Result of fetching and parsing one RSS/Atom feed.
    """

    source_id: str
    source_name: str

    status: str

    http_status: int | None

    articles: tuple[NewsArticle, ...]

    error_message: str | None

    fetched_at: datetime

    @property
    def article_count(self) -> int:
        return len(self.articles)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _entry_value(
        entry: Any,
        field: str,
) -> str | None:
    value = entry.get(field)

    if value is None:
        return None

    value = str(value).strip()

    return value or None


def _parse_entry_datetime(
        entry: Any,
) -> datetime | None:
    """
    Extract the publication timestamp from an RSS/Atom entry.

    feedparser normally exposes parsed timestamps as *_parsed
    structures. We also support string dates as a fallback.
    """

    for field in (
            "published_parsed",
            "updated_parsed",
            "created_parsed",
    ):
        parsed = entry.get(field)

        if parsed is not None:
            try:
                from calendar import timegm

                timestamp = timegm(parsed)

                return datetime.fromtimestamp(
                    timestamp,
                    tz=timezone.utc,
                )
            except (TypeError, ValueError, OverflowError):
                pass

    for field in (
            "published",
            "updated",
            "created",
    ):
        value = _entry_value(
            entry,
            field,
        )

        if not value:
            continue

        try:
            parsed_datetime = parsedate_to_datetime(
                value
            )

            if parsed_datetime.tzinfo is None:
                parsed_datetime = parsed_datetime.replace(
                    tzinfo=timezone.utc
                )

            return parsed_datetime.astimezone(
                timezone.utc
            )
        except (TypeError, ValueError):
            continue

    return None


def _extract_entry_url(
        entry: Any,
) -> str | None:
    """
    Extract the primary article URL from an RSS/Atom entry.
    """

    link = _entry_value(
        entry,
        "link",
    )

    if link:
        return link

    links = entry.get(
        "links",
        [],
    )

    if isinstance(links, list):
        for candidate in links:
            if not isinstance(candidate, dict):
                continue

            href = candidate.get("href")

            if href:
                return str(href).strip()

    return None


def _extract_entry_summary(
        entry: Any,
) -> str | None:
    """
    Extract RSS description/summary/content when available.

    We intentionally store normalized feed text rather than
    downloading the full publisher article page.
    """

    for field in (
            "summary",
            "description",
    ):
        value = _entry_value(
            entry,
            field,
        )

        if value:
            return normalize_text(value)

    content = entry.get(
        "content",
        [],
    )

    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue

            value = item.get("value")

            if value:
                return normalize_text(
                    str(value)
                )

    return None


def _extract_entry_author(
        entry: Any,
) -> str | None:
    author = _entry_value(
        entry,
        "author",
    )

    if author:
        return normalize_text(author)

    return None


def _build_article(
        entry: Any,
        source: NewsSourceConfig,
        fetched_at: datetime,
) -> NewsArticle | None:
    title = _entry_value(
        entry,
        "title",
    )

    url = _extract_entry_url(
        entry
    )

    published_at = _parse_entry_datetime(
        entry
    )

    if not title or not url or not published_at:
        return None

    try:
        canonical_url = canonicalize_url(
            url
        )
    except ValueError:
        return None

    summary = _extract_entry_summary(
        entry
    )

    normalized_title = normalize_text(
        title
    )

    content_hash = build_content_hash(
        normalized_title,
        summary,
    )

    return NewsArticle(
        source=source.name,
        source_type=source.source_type,
        url=url,
        canonical_url=canonical_url,
        title=normalized_title,
        summary=summary,
        published_at=published_at,
        ingested_at=fetched_at,
        content_hash=content_hash,
        language=None,
        author=_extract_entry_author(entry),
        market=source.market,
        symbol=None,
        body=None,
        raw_metadata=None,
    )


def fetch_feed(
        source: NewsSourceConfig,
) -> FeedFetchResult:
    """
    Fetch and parse one configured RSS/Atom feed.

    A feed is classified as:

        HEALTHY -> valid feed with >= 1 article
        EMPTY   -> valid feed with 0 usable articles
        FAILED  -> HTTP/network/parser failure
    """

    fetched_at = _utc_now()

    if not source.feed_url.strip():
        return FeedFetchResult(
            source_id=source.id,
            source_name=source.name,
            status="FAILED",
            http_status=None,
            articles=(),
            error_message="Feed URL is empty.",
            fetched_at=fetched_at,
        )

    request = Request(
        source.feed_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/rss+xml, "
                "application/atom+xml, "
                "application/xml, "
                "text/xml, "
                "*/*;q=0.8"
            ),
        },
        method="GET",
    )

    try:
        with urlopen(
                request,
                timeout=source.timeout_seconds,
        ) as response:
            http_status = response.status

            payload = response.read()

    except HTTPError as exc:
        return FeedFetchResult(
            source_id=source.id,
            source_name=source.name,
            status="FAILED",
            http_status=exc.code,
            articles=(),
            error_message=(
                f"HTTP {exc.code}: {exc.reason}"
            ),
            fetched_at=fetched_at,
        )

    except (URLError, TimeoutError, OSError) as exc:
        return FeedFetchResult(
            source_id=source.id,
            source_name=source.name,
            status="FAILED",
            http_status=None,
            articles=(),
            error_message=str(exc),
            fetched_at=fetched_at,
        )

    parsed = feedparser.parse(
        payload
    )

    if getattr(
            parsed,
            "bozo",
            False,
    ):
        bozo_exception = getattr(
            parsed,
            "bozo_exception",
            None,
        )

        return FeedFetchResult(
            source_id=source.id,
            source_name=source.name,
            status="FAILED",
            http_status=http_status,
            articles=(),
            error_message=(
                f"Invalid RSS/Atom feed: "
                f"{bozo_exception}"
            ),
            fetched_at=fetched_at,
        )

    entries = getattr(
        parsed,
        "entries",
        [],
    )

    articles: list[NewsArticle] = []

    for entry in entries[
        : source.max_articles_per_feed
    ]:
        article = _build_article(
            entry=entry,
            source=source,
            fetched_at=fetched_at,
        )

        if article is not None:
            articles.append(
                article
            )

    status = (
        "HEALTHY"
        if articles
        else "EMPTY"
    )

    return FeedFetchResult(
        source_id=source.id,
        source_name=source.name,
        status=status,
        http_status=http_status,
        articles=tuple(articles),
        error_message=None,
        fetched_at=fetched_at,
    )