from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from marketlens.db import connect, initialize_database
from marketlens.news import FeedFetchResult
from marketlens.news.ingestion import (
    _deduplicate_articles,
    _filter_articles_to_window,
    ingest_news,
)
from marketlens.news.models import NewsArticle


TEST_NOW = datetime(
    2026,
    9,
    23,
    12,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture(autouse=True)
def freeze_ingestion_clock(
        monkeypatch,
) -> None:
    """
    Keep ingestion tests deterministic.

    Production ingestion uses the real UTC clock. Tests use a fixed
    starting timestamp so the 72-hour catch-up window does not depend
    on the actual date on which the tests are executed.

    The clock advances by one second on each call so multiple
    ingestion runs have distinct run_at timestamps.
    """
    current_time = TEST_NOW

    def fake_utc_now() -> datetime:
        nonlocal current_time

        result = current_time
        current_time = current_time + timedelta(seconds=1)

        return result

    monkeypatch.setattr(
        "marketlens.news.ingestion._utc_now",
        fake_utc_now,
    )


def _article(
        article_id_seed: str,
        published_at: datetime,
) -> NewsArticle:
    return NewsArticle(
        source="Test Source",
        source_type="publisher",
        url=f"https://example.com/{article_id_seed}",
        canonical_url=f"https://example.com/{article_id_seed}",
        title=f"Test Article {article_id_seed}",
        summary="Test summary",
        published_at=published_at,
        ingested_at=datetime.now(timezone.utc),
        content_hash=f"hash-{article_id_seed}",
    )


def test_deduplicate_articles_removes_duplicate_article_ids() -> None:
    published_at = datetime(
        2026,
        9,
        22,
        10,
        0,
        tzinfo=timezone.utc,
    )

    first = _article(
        article_id_seed="one",
        published_at=published_at,
    )

    duplicate = NewsArticle(
        source="Another Source",
        source_type="publisher",
        url=first.url,
        canonical_url=first.canonical_url,
        title=first.title,
        summary=first.summary,
        published_at=first.published_at,
        ingested_at=first.ingested_at,
        content_hash=first.content_hash,
    )

    second = _article(
        article_id_seed="two",
        published_at=published_at,
    )

    result = _deduplicate_articles(
        [first, duplicate, second]
    )

    assert len(result) == 2
    assert result[0].article_id == first.article_id
    assert result[1].article_id == second.article_id


def test_filter_articles_to_window_keeps_only_articles_in_window() -> None:
    window_start = datetime(
        2026,
        9,
        22,
        10,
        0,
        tzinfo=timezone.utc,
    )

    window_end = datetime(
        2026,
        9,
        22,
        12,
        0,
        tzinfo=timezone.utc,
    )

    before = _article(
        article_id_seed="before",
        published_at=window_start - timedelta(minutes=1),
    )

    inside = _article(
        article_id_seed="inside",
        published_at=window_start + timedelta(minutes=30),
    )

    at_end = _article(
        article_id_seed="at-end",
        published_at=window_end,
    )

    result = _filter_articles_to_window(
        articles=[before, inside, at_end],
        window_start=window_start,
        window_end=window_end,
    )

    assert len(result) == 1
    assert result[0].article_id == inside.article_id


def test_filter_articles_to_window_accepts_naive_publication_time() -> None:
    window_start = datetime(
        2026,
        9,
        22,
        10,
        0,
        tzinfo=timezone.utc,
    )

    window_end = datetime(
        2026,
        9,
        22,
        12,
        0,
        tzinfo=timezone.utc,
    )

    article = _article(
        article_id_seed="naive",
        published_at=datetime(
            2026,
            9,
            22,
            11,
            0,
        ),
    )

    result = _filter_articles_to_window(
        articles=[article],
        window_start=window_start,
        window_end=window_end,
    )

    assert len(result) == 1


def test_ingest_news_reports_global_article_accounting() -> None:
    published_at = datetime(
        2026,
        9,
        23,
        10,
        0,
        tzinfo=timezone.utc,
    )

    articles = [
        _article(
            article_id_seed="accounting-one",
            published_at=published_at,
        ),
        _article(
            article_id_seed="accounting-two",
            published_at=published_at,
        ),
        _article(
            article_id_seed="accounting-three",
            published_at=published_at,
        ),
    ]

    class FakeSource:
        id = "test-source"
        name = "Test Source"

    feed_result = FeedFetchResult(
        source_id="test-source",
        source_name="Test Source",
        status="HEALTHY",
        http_status=200,
        articles=tuple(articles),
        error_message=None,
        fetched_at=published_at,
    )

    with (
        pytest.MonkeyPatch.context() as monkeypatch,
    ):
        monkeypatch.setattr(
            "marketlens.news.ingestion.enabled_news_sources",
            lambda: [FakeSource()],
        )

        monkeypatch.setattr(
            "marketlens.news.ingestion.fetch_feed",
            lambda source: feed_result,
        )

        monkeypatch.setattr(
            "marketlens.news.ingestion.count_existing_articles",
            lambda articles, db_path=None: 1,
        )

        monkeypatch.setattr(
            "marketlens.news.ingestion.upsert_articles",
            lambda articles, db_path=None: len(articles),
        )

        monkeypatch.setattr(
            "marketlens.news.ingestion.write_run_log",
            lambda *args, **kwargs: None,
        )

        result = ingest_news(
            catch_up_hours=72,
        )

    assert result.sources_attempted == 1
    assert result.sources_healthy == 1
    assert result.sources_empty == 0
    assert result.sources_failed == 0

    assert result.articles_fetched == 3
    assert result.articles_unique == 3
    assert result.articles_existing == 1
    assert result.articles_inserted == 2


def test_ingest_news_writes_success_run_log(
        monkeypatch,
) -> None:
    published_at = datetime(
        2026,
        9,
        23,
        10,
        0,
        tzinfo=timezone.utc,
    )

    articles = [
        _article(
            article_id_seed="run-log-one",
            published_at=published_at,
        ),
        _article(
            article_id_seed="run-log-two",
            published_at=published_at,
        ),
        _article(
            article_id_seed="run-log-three",
            published_at=published_at,
        ),
    ]

    class FakeSource:
        id = "test-source"
        name = "Test Source"

    feed_result = FeedFetchResult(
        source_id="test-source",
        source_name="Test Source",
        status="HEALTHY",
        http_status=200,
        articles=tuple(articles),
        error_message=None,
        fetched_at=published_at,
    )

    captured_log: dict[str, object] = {}

    def fake_write_run_log(
            stage: str,
            status: str,
            rows: int | None = None,
            detail: str | None = None,
            run_at: datetime | None = None,
            db_path=None,
    ) -> None:
        captured_log["stage"] = stage
        captured_log["status"] = status
        captured_log["rows"] = rows
        captured_log["detail"] = detail
        captured_log["run_at"] = run_at
        captured_log["db_path"] = db_path

    monkeypatch.setattr(
        "marketlens.news.ingestion.enabled_news_sources",
        lambda: [FakeSource()],
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.fetch_feed",
        lambda source: feed_result,
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.count_existing_articles",
        lambda articles, db_path=None: 1,
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.upsert_articles",
        lambda articles, db_path=None: len(articles),
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.write_run_log",
        fake_write_run_log,
    )

    result = ingest_news(
        catch_up_hours=72,
    )

    assert result.articles_fetched == 3
    assert result.articles_unique == 3
    assert result.articles_existing == 1
    assert result.articles_inserted == 2

    assert captured_log["stage"] == "NEWS_INGESTION"
    assert captured_log["status"] == "SUCCESS"
    assert captured_log["rows"] == 2

    assert captured_log["detail"] == (
        "fetched=3; unique=3; "
        "existing=1; inserted=2; sources=1"
    )

    assert isinstance(
        captured_log["run_at"],
        datetime,
    )


def test_ingest_news_writes_failed_run_log_and_reraises(
        monkeypatch,
) -> None:
    class FakeSource:
        id = "failing-source"
        name = "Failing Source"

    captured_log: dict[str, object] = {}

    def fake_write_run_log(
            stage: str,
            status: str,
            rows: int | None = None,
            detail: str | None = None,
            run_at: datetime | None = None,
            db_path=None,
    ) -> None:
        captured_log["stage"] = stage
        captured_log["status"] = status
        captured_log["rows"] = rows
        captured_log["detail"] = detail
        captured_log["run_at"] = run_at
        captured_log["db_path"] = db_path

    expected_error = RuntimeError(
        "simulated feed failure"
    )

    def failing_fetch_feed(source):
        raise expected_error

    monkeypatch.setattr(
        "marketlens.news.ingestion.enabled_news_sources",
        lambda: [FakeSource()],
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.fetch_feed",
        failing_fetch_feed,
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.write_run_log",
        fake_write_run_log,
    )

    with pytest.raises(
            RuntimeError,
            match="simulated feed failure",
    ):
        ingest_news(
            catch_up_hours=72,
        )

    assert captured_log["stage"] == "NEWS_INGESTION"
    assert captured_log["status"] == "FAILED"
    assert captured_log["rows"] == 0

    assert captured_log["detail"] == (
        "error=RuntimeError: simulated feed failure"
    )

    assert isinstance(
        captured_log["run_at"],
        datetime,
    )


def test_ingest_news_persists_articles_and_run_log(
        monkeypatch,
        tmp_path,
) -> None:
    db_path = tmp_path / "news_ingestion_test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    published_at = datetime(
        2026,
        9,
        23,
        10,
        0,
        tzinfo=timezone.utc,
    )

    articles = [
        _article(
            article_id_seed="integration-one",
            published_at=published_at,
        ),
        _article(
            article_id_seed="integration-two",
            published_at=published_at,
        ),
    ]

    class FakeSource:
        id = "integration-source"
        name = "Integration Source"

    feed_result = FeedFetchResult(
        source_id="integration-source",
        source_name="Integration Source",
        status="HEALTHY",
        http_status=200,
        articles=tuple(articles),
        error_message=None,
        fetched_at=published_at,
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.enabled_news_sources",
        lambda: [FakeSource()],
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.fetch_feed",
        lambda source: feed_result,
    )

    result = ingest_news(
        catch_up_hours=72,
        db_path=db_path,
    )

    assert result.articles_fetched == 2
    assert result.articles_unique == 2
    assert result.articles_existing == 0
    assert result.articles_inserted == 2

    with connect(db_path) as connection:
        article_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM articles
            """
        ).fetchone()[0]

        run_log_row = connection.execute(
            """
            SELECT
                stage,
                status,
                rows,
                detail
            FROM run_log
            WHERE stage = ?
            ORDER BY run_at DESC
                LIMIT 1
            """,
            ["NEWS_INGESTION"],
        ).fetchone()

    assert article_count == 2

    assert run_log_row is not None
    assert run_log_row[0] == "NEWS_INGESTION"
    assert run_log_row[1] == "SUCCESS"
    assert run_log_row[2] == 2
    assert run_log_row[3] == (
        "fetched=2; unique=2; "
        "existing=0; inserted=2; sources=1"
    )


def test_ingest_news_is_idempotent_across_repeated_runs(
        monkeypatch,
        tmp_path,
) -> None:
    db_path = tmp_path / "news_idempotency_test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    published_at = datetime(
        2026,
        9,
        23,
        10,
        0,
        tzinfo=timezone.utc,
    )

    articles = [
        _article(
            article_id_seed="idempotency-one",
            published_at=published_at,
        ),
        _article(
            article_id_seed="idempotency-two",
            published_at=published_at,
        ),
    ]

    class FakeSource:
        id = "idempotency-source"
        name = "Idempotency Source"

    feed_result = FeedFetchResult(
        source_id="idempotency-source",
        source_name="Idempotency Source",
        status="HEALTHY",
        http_status=200,
        articles=tuple(articles),
        error_message=None,
        fetched_at=published_at,
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.enabled_news_sources",
        lambda: [FakeSource()],
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.fetch_feed",
        lambda source: feed_result,
    )

    first_result = ingest_news(
        catch_up_hours=72,
        db_path=db_path,
    )

    assert first_result.articles_fetched == 2
    assert first_result.articles_unique == 2
    assert first_result.articles_existing == 0
    assert first_result.articles_inserted == 2

    second_result = ingest_news(
        catch_up_hours=72,
        db_path=db_path,
    )

    assert second_result.articles_fetched == 2
    assert second_result.articles_unique == 2
    assert second_result.articles_existing == 2
    assert second_result.articles_inserted == 0

    with connect(db_path) as connection:
        article_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM articles
            """
        ).fetchone()[0]

        run_log_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM run_log
            WHERE stage = ?
            """,
            ["NEWS_INGESTION"],
        ).fetchone()[0]

        latest_run_log = connection.execute(
            """
            SELECT
                status,
                rows
            FROM run_log
            WHERE stage = ?
            ORDER BY run_at DESC
                LIMIT 1
            """,
            ["NEWS_INGESTION"],
        ).fetchone()

    assert article_count == 2
    assert run_log_count == 2

    assert latest_run_log is not None
    assert latest_run_log[0] == "SUCCESS"
    assert latest_run_log[1] == 0


def test_ingest_news_persists_failed_run_log_on_exception(
        monkeypatch,
        tmp_path,
) -> None:
    db_path = tmp_path / "news_failed_run_log_test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    class FakeSource:
        id = "failing-source"
        name = "Failing Source"

    monkeypatch.setattr(
        "marketlens.news.ingestion.enabled_news_sources",
        lambda: [FakeSource()],
    )

    def fake_fetch_feed(source):
        raise RuntimeError("simulated feed failure")

    monkeypatch.setattr(
        "marketlens.news.ingestion.fetch_feed",
        fake_fetch_feed,
    )

    with pytest.raises(
            RuntimeError,
            match="simulated feed failure",
    ):
        ingest_news(
            catch_up_hours=72,
            db_path=db_path,
        )

    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                stage,
                status,
                rows,
                detail
            FROM run_log
            WHERE stage = ?
            ORDER BY run_at DESC
                LIMIT 1
            """,
            ["NEWS_INGESTION"],
        ).fetchone()

    assert row is not None

    assert row[0] == "NEWS_INGESTION"
    assert row[1] == "FAILED"
    assert row[2] == 0
    assert row[3] == (
        "error=RuntimeError: simulated feed failure"
    )


def test_ingest_news_handles_empty_source(
        monkeypatch,
        tmp_path,
) -> None:
    db_path = tmp_path / "news_empty_source_test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    class FakeSource:
        id = "empty-source"
        name = "Empty Source"

    feed_result = FeedFetchResult(
        source_id="empty-source",
        source_name="Empty Source",
        status="EMPTY",
        http_status=200,
        articles=tuple(),
        error_message=None,
        fetched_at=datetime(
            2026,
            9,
            23,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.enabled_news_sources",
        lambda: [FakeSource()],
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.fetch_feed",
        lambda source: feed_result,
    )

    result = ingest_news(
        catch_up_hours=72,
        db_path=db_path,
    )

    assert result.sources_attempted == 1
    assert result.sources_healthy == 0
    assert result.sources_empty == 1
    assert result.sources_failed == 0

    assert result.articles_fetched == 0
    assert result.articles_unique == 0
    assert result.articles_existing == 0
    assert result.articles_inserted == 0

    assert len(result.source_results) == 1

    source_result = result.source_results[0]

    assert source_result.source_id == "empty-source"
    assert source_result.source_name == "Empty Source"
    assert source_result.status == "EMPTY"
    assert source_result.http_status == 200
    assert source_result.fetched_articles == 0
    assert source_result.unique_articles == 0
    assert source_result.error_message is None

    with connect(db_path) as connection:
        article_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM articles
            """
        ).fetchone()[0]

        run_log = connection.execute(
            """
            SELECT
                status,
                rows,
                detail
            FROM run_log
            WHERE stage = ?
            ORDER BY run_at DESC
                LIMIT 1
            """,
            ["NEWS_INGESTION"],
        ).fetchone()

    assert article_count == 0

    assert run_log is not None
    assert run_log[0] == "SUCCESS"
    assert run_log[1] == 0
    assert run_log[2] == (
        "fetched=0; "
        "unique=0; "
        "existing=0; "
        "inserted=0; "
        "sources=1"
    )


def test_ingest_news_tracks_failed_source_without_raising(
        monkeypatch,
        tmp_path,
) -> None:
    db_path = tmp_path / "news_failed_source_test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    class FailedSource:
        id = "failed-source"
        name = "Failed Source"

    class HealthySource:
        id = "healthy-source"
        name = "Healthy Source"

    failed_result = FeedFetchResult(
        source_id="failed-source",
        source_name="Failed Source",
        status="FAILED",
        http_status=503,
        articles=tuple(),
        error_message="HTTP 503 Service Unavailable",
        fetched_at=datetime(
            2026,
            9,
            23,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    healthy_result = FeedFetchResult(
        source_id="healthy-source",
        source_name="Healthy Source",
        status="HEALTHY",
        http_status=200,
        articles=tuple(),
        error_message=None,
        fetched_at=datetime(
            2026,
            9,
            23,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    monkeypatch.setattr(
        "marketlens.news.ingestion.enabled_news_sources",
        lambda: [
            FailedSource(),
            HealthySource(),
        ],
    )

    def fake_fetch_feed(source):
        if source.id == "failed-source":
            return failed_result

        return healthy_result

    monkeypatch.setattr(
        "marketlens.news.ingestion.fetch_feed",
        fake_fetch_feed,
    )

    result = ingest_news(
        catch_up_hours=72,
        db_path=db_path,
    )

    assert result.sources_attempted == 2
    assert result.sources_healthy == 1
    assert result.sources_empty == 0
    assert result.sources_failed == 1

    assert result.articles_fetched == 0
    assert result.articles_unique == 0
    assert result.articles_existing == 0
    assert result.articles_inserted == 0

    assert len(result.source_results) == 2

    failed_source_result = result.source_results[0]

    assert failed_source_result.source_id == "failed-source"
    assert failed_source_result.status == "FAILED"
    assert failed_source_result.http_status == 503
    assert failed_source_result.fetched_articles == 0
    assert failed_source_result.unique_articles == 0
    assert (
            failed_source_result.error_message
            == "HTTP 503 Service Unavailable"
    )

    healthy_source_result = result.source_results[1]

    assert healthy_source_result.source_id == "healthy-source"
    assert healthy_source_result.status == "HEALTHY"
    assert healthy_source_result.http_status == 200

    with connect(db_path) as connection:
        run_log = connection.execute(
            """
            SELECT
                status,
                rows,
                detail
            FROM run_log
            WHERE stage = ?
            ORDER BY run_at DESC
                LIMIT 1
            """,
            ["NEWS_INGESTION"],
        ).fetchone()

    assert run_log is not None

    # Current behavior: source-level FAILED results do not
    # raise an exception, so the ingestion run is recorded
    # as SUCCESS while sources_failed exposes the source problem.
    assert run_log[0] == "SUCCESS"
    assert run_log[1] == 0


def test_ingest_news_rejects_non_positive_catch_up_hours(
        tmp_path,
) -> None:
    db_path = tmp_path / "news_invalid_window_test.duckdb"

    initialize_database(
        db_path=db_path,
    )

    with pytest.raises(
            ValueError,
            match="catch_up_hours must be greater than zero.",
    ):
        ingest_news(
            catch_up_hours=0,
            db_path=db_path,
        )

    with pytest.raises(
            ValueError,
            match="catch_up_hours must be greater than zero.",
    ):
        ingest_news(
            catch_up_hours=-1,
            db_path=db_path,
        )

    with connect(db_path) as connection:
        run_log_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM run_log
            WHERE stage = ?
            """,
            ["NEWS_INGESTION"],
        ).fetchone()[0]

    assert run_log_count == 0