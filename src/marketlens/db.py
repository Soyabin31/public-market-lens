from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from marketlens.config import DATA_DIR


DATABASE_FILENAME = "market.duckdb"


def get_db_path() -> Path:
    """
    Return the absolute path of the Market Lens DuckDB database.
    """
    return DATA_DIR / DATABASE_FILENAME


def connect(db_path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """
    Open a connection to the Market Lens DuckDB database.

    If db_path is not supplied, the normal application database
    under data/market.duckdb is used.

    A custom path is useful for tests so that tests do not
    modify the real application database.
    """
    if db_path is None:
        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    return duckdb.connect(str(db_path))


def write_run_log(
        stage: str,
        status: str,
        rows: int | None = None,
        detail: str | None = None,
        run_at: datetime | None = None,
        db_path: Path | None = None,
) -> None:
    """
    Write one pipeline execution record to run_log.
    """
    timestamp = (
        run_at
        if run_at is not None
        else datetime.now(timezone.utc)
    )

    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO run_log (
                run_at,
                stage,
                status,
                rows,
                detail
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                timestamp,
                stage,
                status,
                rows,
                detail,
            ],
        )


def initialize_schema(con: duckdb.DuckDBPyConnection) -> None:
    """
    Create all core Market Lens tables if they do not already exist.

    This function is intentionally idempotent:
    calling it multiple times must be safe.
    """

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS prices (
                                              symbol VARCHAR NOT NULL,
                                              date DATE NOT NULL,
                                              open DOUBLE,
                                              high DOUBLE,
                                              low DOUBLE,
                                              close DOUBLE,
                                              volume BIGINT,
                                              source VARCHAR NOT NULL,
                                              PRIMARY KEY (symbol, date)
            )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
                                                article_id VARCHAR PRIMARY KEY,

                                                source VARCHAR NOT NULL,
                                                source_type VARCHAR NOT NULL,

                                                url VARCHAR NOT NULL,
                                                canonical_url VARCHAR NOT NULL,

                                                title VARCHAR NOT NULL,
                                                summary VARCHAR,
                                                body VARCHAR,

                                                published_at TIMESTAMP NOT NULL,
                                                ingested_at TIMESTAMP NOT NULL,

                                                content_hash VARCHAR NOT NULL,

                                                language VARCHAR,
                                                author VARCHAR,

                                                market VARCHAR,
                                                symbol VARCHAR,

                                                raw_metadata VARCHAR
        )
        """
    )

    # ---------------------------------------------------------
    # Existing-database schema upgrades
    #
    # These columns were added after the original articles table
    # was created. IF NOT EXISTS keeps the upgrade idempotent.
    # ---------------------------------------------------------

    con.execute(
        """
        ALTER TABLE articles
            ADD COLUMN IF NOT EXISTS geography VARCHAR
        """
    )

    con.execute(
        """
        ALTER TABLE articles
            ADD COLUMN IF NOT EXISTS asset_class VARCHAR
        """
    )

    con.execute(
        """
        ALTER TABLE articles
            ADD COLUMN IF NOT EXISTS category VARCHAR
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS article_tags (
                                                    content_hash VARCHAR NOT NULL,
                                                    model_name VARCHAR NOT NULL,
                                                    event_type VARCHAR NOT NULL,
                                                    sentiment DOUBLE,
                                                    direction VARCHAR,
                                                    confidence DOUBLE,
                                                    countries VARCHAR,
                                                    sectors VARCHAR,
                                                    rationale VARCHAR,
                                                    tagged_at TIMESTAMP NOT NULL,
                                                    PRIMARY KEY (content_hash, model_name)
            )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS features (
                                                symbol VARCHAR NOT NULL,
                                                date DATE NOT NULL,
                                                feature_name VARCHAR NOT NULL,
                                                value DOUBLE,
                                                PRIMARY KEY (symbol, date, feature_name)
            )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
                                                   symbol VARCHAR NOT NULL,
                                                   date DATE NOT NULL,
                                                   horizon_days INTEGER NOT NULL,
                                                   prob_up DOUBLE NOT NULL,
                                                   model_version VARCHAR NOT NULL,
                                                   created_at TIMESTAMP NOT NULL,
                                                   realised_direction INTEGER,
                                                   realised_return DOUBLE,
                                                   PRIMARY KEY (symbol, date, horizon_days)
            )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS mood_history (
                                                    symbol VARCHAR NOT NULL,
                                                    date DATE NOT NULL,
                                                    score DOUBLE NOT NULL,
                                                    label VARCHAR NOT NULL,
                                                    components VARCHAR,
                                                    PRIMARY KEY (symbol, date)
            )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS run_log (
                                               run_at TIMESTAMP NOT NULL,
                                               stage VARCHAR NOT NULL,
                                               status VARCHAR NOT NULL,
                                               rows INTEGER,
                                               detail VARCHAR
        )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS holdings (
                                                snapshot_date DATE NOT NULL,
                                                symbol VARCHAR NOT NULL,
                                                qty DOUBLE NOT NULL,
                                                avg_price DOUBLE,
                                                broker VARCHAR NOT NULL,
                                                PRIMARY KEY (snapshot_date, symbol, broker)
            )
        """
    )

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS breadth_history (
                                                       market VARCHAR NOT NULL,
                                                       date DATE NOT NULL,

                                                       advances INTEGER NOT NULL,
                                                       declines INTEGER NOT NULL,
                                                       unchanged INTEGER NOT NULL,
                                                       total_stocks INTEGER NOT NULL,

                                                       advance_pct DOUBLE,
                                                       decline_pct DOUBLE,
                                                       net_advances INTEGER,
                                                       ad_ratio DOUBLE,

                                                       mean_return DOUBLE,
                                                       median_return DOUBLE,
                                                       return_dispersion DOUBLE,
                                                       pct_above_1pct DOUBLE,
                                                       pct_below_minus_1pct DOUBLE,

                                                       advancing_volume DOUBLE,
                                                       declining_volume DOUBLE,
                                                       total_volume DOUBLE,
                                                       up_down_volume_ratio DOUBLE,
                                                       volume_participation DOUBLE,

                                                       benchmark_return DOUBLE,
                                                       breadth_index_divergence DOUBLE,

                                                       vix_close DOUBLE,
                                                       vix_return DOUBLE,
                                                       vix_change DOUBLE,

                                                       PRIMARY KEY (market, date)
            )
        """
    )


def initialize_database(db_path: Path | None = None) -> Path:
    """
    Create the database file and initialize its schema.

    If db_path is not supplied, the normal application database
    under data/market.duckdb is used.

    Returns:
        Path to the initialized DuckDB database.
    """
    if db_path is None:
        db_path = get_db_path()

    with connect(db_path) as con:
        initialize_schema(con)

    return db_path

def upsert_prices(
        df: pd.DataFrame,
        db_path: Path | None = None,
) -> int:
    """
    Insert or update price records in the prices table.

    The primary key is (symbol, date), so running the same
    ingestion repeatedly is safe and idempotent.

    Returns:
        Number of rows supplied to the upsert operation.
    """
    if df.empty:
        return 0

    required_columns = {
        "symbol",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required price columns: {sorted(missing)}"
        )

    rows = df[
        [
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "source",
        ]
    ].copy()

    with connect(db_path) as con:
        con.register("price_rows", rows)

        con.execute(
            """
            INSERT INTO prices (
                symbol,
                date,
                open,
                high,
                low,
                close,
                volume,
                source
            )
            SELECT
                symbol,
                date,
                open,
                high,
                low,
                close,
                volume,
                source
            FROM price_rows
            ON CONFLICT (symbol, date)
                DO UPDATE SET
                       open = EXCLUDED.open,
                       high = EXCLUDED.high,
                       low = EXCLUDED.low,
                       close = EXCLUDED.close,
                       volume = EXCLUDED.volume,
                       source = EXCLUDED.source
            """
        )

    return len(rows)


def read_prices(
        symbol: str,
        db_path: Path | None = None,
) -> pd.DataFrame:
    """
    Read all stored daily prices for one symbol.

    Results are ordered chronologically by date.
    """
    with connect(db_path) as con:
        return con.execute(
            """
            SELECT
                symbol,
                date,
                open,
                high,
                low,
                close,
                volume,
                source
            FROM prices
            WHERE symbol = ?
            ORDER BY date
            """,
            [symbol],
        ).df()


def upsert_breadth(
        df: pd.DataFrame,
        market: str,
        db_path: Path | None = None,
) -> int:
    """
    Insert or update calculated market breadth.

    Breadth is uniquely identified by:

        market + date

    The supplied DataFrame is treated as the authoritative
    calculation for its date range.

    Existing breadth rows inside that recalculated date range
    are removed before the new calculation is inserted. This
    prevents stale derived rows from surviving after changes
    such as market-calendar corrections.
    """

    if df.empty:
        return 0

    required_columns = {
        "date",
        "advances",
        "declines",
        "unchanged",
        "total_stocks",
        "advance_pct",
        "decline_pct",
        "net_advances",
        "ad_ratio",
        "mean_return",
        "median_return",
        "return_dispersion",
        "pct_above_1pct",
        "pct_below_minus_1pct",
        "advancing_volume",
        "declining_volume",
        "total_volume",
        "up_down_volume_ratio",
        "volume_participation",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required breadth columns: {sorted(missing)}"
        )

    rows = df.copy()

    rows["market"] = market

    rows["date"] = pd.to_datetime(rows["date"]).dt.normalize()

    optional_columns = [
        "benchmark_return",
        "breadth_index_divergence",
        "vix_close",
        "vix_return",
        "vix_change",
    ]

    for column in optional_columns:
        if column not in rows.columns:
            rows[column] = None

    rows = rows[
        [
            "market",
            "date",
            "advances",
            "declines",
            "unchanged",
            "total_stocks",
            "advance_pct",
            "decline_pct",
            "net_advances",
            "ad_ratio",
            "mean_return",
            "median_return",
            "return_dispersion",
            "pct_above_1pct",
            "pct_below_minus_1pct",
            "advancing_volume",
            "declining_volume",
            "total_volume",
            "up_down_volume_ratio",
            "volume_participation",
            "benchmark_return",
            "breadth_index_divergence",
            "vix_close",
            "vix_return",
            "vix_change",
        ]
    ].copy()

    start_date = rows["date"].min()
    end_date = rows["date"].max()

    with connect(db_path) as con:
        # The new calculation is authoritative for this market
        # and date range. Remove any older derived rows first.
        con.execute(
            """
            DELETE FROM breadth_history
            WHERE market = ?
              AND date BETWEEN ? AND ?
            """,
            [
                market,
                start_date.date(),
                end_date.date(),
            ],
        )

        con.register("breadth_rows", rows)

        con.execute(
            """
            INSERT INTO breadth_history (
                market,
                date,
                advances,
                declines,
                unchanged,
                total_stocks,
                advance_pct,
                decline_pct,
                net_advances,
                ad_ratio,
                mean_return,
                median_return,
                return_dispersion,
                pct_above_1pct,
                pct_below_minus_1pct,
                advancing_volume,
                declining_volume,
                total_volume,
                up_down_volume_ratio,
                volume_participation,
                benchmark_return,
                breadth_index_divergence,
                vix_close,
                vix_return,
                vix_change
            )
            SELECT
                market,
                date,
                advances,
                declines,
                unchanged,
                total_stocks,
                advance_pct,
                decline_pct,
                net_advances,
                ad_ratio,
                mean_return,
                median_return,
                return_dispersion,
                pct_above_1pct,
                pct_below_minus_1pct,
                advancing_volume,
                declining_volume,
                total_volume,
                up_down_volume_ratio,
                volume_participation,
                benchmark_return,
                breadth_index_divergence,
                vix_close,
                vix_return,
                vix_change
            FROM breadth_rows
            ON CONFLICT (market, date)
                DO UPDATE SET
                advances = EXCLUDED.advances,
                       declines = EXCLUDED.declines,
                       unchanged = EXCLUDED.unchanged,
                       total_stocks = EXCLUDED.total_stocks,
                       advance_pct = EXCLUDED.advance_pct,
                       decline_pct = EXCLUDED.decline_pct,
                       net_advances = EXCLUDED.net_advances,
                       ad_ratio = EXCLUDED.ad_ratio,
                       mean_return = EXCLUDED.mean_return,
                       median_return = EXCLUDED.median_return,
                       return_dispersion = EXCLUDED.return_dispersion,
                       pct_above_1pct = EXCLUDED.pct_above_1pct,
                       pct_below_minus_1pct = EXCLUDED.pct_below_minus_1pct,
                       advancing_volume = EXCLUDED.advancing_volume,
                       declining_volume = EXCLUDED.declining_volume,
                       total_volume = EXCLUDED.total_volume,
                       up_down_volume_ratio = EXCLUDED.up_down_volume_ratio,
                       volume_participation = EXCLUDED.volume_participation,
                       benchmark_return = EXCLUDED.benchmark_return,
                       breadth_index_divergence = EXCLUDED.breadth_index_divergence,
                       vix_close = EXCLUDED.vix_close,
                       vix_return = EXCLUDED.vix_return,
                       vix_change = EXCLUDED.vix_change
            """
        )

    return len(rows)


def upsert_mood_history(
        df: pd.DataFrame,
        symbol: str,
        db_path: Path | None = None,
) -> int:
    """
    Insert or replace calculated market mood.

    The supplied DataFrame is authoritative for its date range.
    Existing mood rows for that symbol and date range are removed
    before the new calculation is inserted.

    This prevents stale derived mood rows from surviving after
    calendar or breadth corrections.
    """

    if df.empty:
        return 0

    required_columns = {
        "date",
        "score",
        "label",
        "components",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required mood columns: {sorted(missing)}"
        )

    rows = df.copy()

    rows["symbol"] = symbol

    rows["date"] = (
        pd.to_datetime(rows["date"])
        .dt.normalize()
    )

    rows = rows[
        [
            "symbol",
            "date",
            "score",
            "label",
            "components",
        ]
    ].copy()

    start_date = rows["date"].min()
    end_date = rows["date"].max()

    with connect(db_path) as con:
        con.execute(
            """
            DELETE FROM mood_history
            WHERE symbol = ?
              AND date BETWEEN ? AND ?
            """,
            [
                symbol,
                start_date.date(),
                end_date.date(),
            ],
        )

        con.register(
            "mood_rows",
            rows,
        )

        con.execute(
            """
            INSERT INTO mood_history (
                symbol,
                date,
                score,
                label,
                components
            )
            SELECT
                symbol,
                date,
                score,
                label,
                components
            FROM mood_rows
            ON CONFLICT (symbol, date)
                DO UPDATE SET
                score = EXCLUDED.score,
                       label = EXCLUDED.label,
                       components = EXCLUDED.components
            """
        )

    return len(rows)


def read_breadth(
        market: str,
        db_path: Path | None = None,
) -> pd.DataFrame:
    """
    Read stored market breadth chronologically.
    """

    with connect(db_path) as con:
        return con.execute(
            """
            SELECT
                market,
                date,
                advances,
                declines,
                unchanged,
                total_stocks,
                advance_pct,
                decline_pct,
                net_advances,
                ad_ratio,
                mean_return,
                median_return,
                return_dispersion,
                pct_above_1pct,
                pct_below_minus_1pct,
                advancing_volume,
                declining_volume,
                total_volume,
                up_down_volume_ratio,
                volume_participation,
                benchmark_return,
                breadth_index_divergence,
                vix_close,
                vix_return,
                vix_change
            FROM breadth_history
            WHERE market = ?
            ORDER BY date
            """,
            [market],
        ).df()

def test_write_run_log_persists_pipeline_execution(tmp_path) -> None:
    from marketlens.db import initialize_database, write_run_log

    db_path = tmp_path / "run-log-test.duckdb"

    initialize_database(db_path)

    write_run_log(
        stage="NEWS_INGESTION",
        status="SUCCESS",
        rows=13,
        detail="fetched=132; unique=132; existing=119; inserted=13",
        db_path=db_path,
    )

    from marketlens.db import connect

    with connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                stage,
                status,
                rows,
                detail
            FROM run_log
            """
        ).fetchone()

    assert row is not None
    assert row[0] == "NEWS_INGESTION"
    assert row[1] == "SUCCESS"
    assert row[2] == 13
    assert row[3] == (
        "fetched=132; unique=132; "
        "existing=119; inserted=13"
    )