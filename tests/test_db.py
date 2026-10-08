from datetime import datetime
from pathlib import Path
import pandas as pd

from marketlens.db import connect, initialize_schema
from marketlens.db import upsert_prices


def test_database_schema_is_created(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"

    with connect(db_path) as con:
        initialize_schema(con)

        tables = con.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
            """
        ).fetchall()

    table_names = {row[0] for row in tables}

    expected_tables = {
        "prices",
        "articles",
        "article_tags",
        "features",
        "predictions",
        "mood_history",
        "run_log",
        "holdings",
    }

    assert expected_tables.issubset(table_names)


def test_database_initialization_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"

    with connect(db_path) as con:
        initialize_schema(con)
        initialize_schema(con)

        result = con.execute(
            "SELECT COUNT(*) FROM prices"
        ).fetchone()

    assert result[0] == 0


def test_price_insert_and_read(tmp_path: Path):
    db_path = tmp_path / "test.duckdb"

    with connect(db_path) as con:
        initialize_schema(con)

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "^NSEI",
                datetime(2026, 9, 16).date(),
                25000.0,
                25200.0,
                24900.0,
                25150.0,
                1000000,
                "test",
            ],
        )

        row = con.execute(
            """
            SELECT symbol, close, volume, source
            FROM prices
            WHERE symbol = ?
              AND date = ?
            """,
            [
                "^NSEI",
                datetime(2026, 9, 16).date(),
            ],
        ).fetchone()

    assert row == ("^NSEI", 25150.0, 1000000, "test")


def test_upsert_prices_is_idempotent(tmp_path):
    db_path = tmp_path / "prices.duckdb"

    df = pd.DataFrame(
        [
            {
                "symbol": "^NSEI",
                "date": "2026-09-18",
                "open": 100.0,
                "high": 105.0,
                "low": 99.0,
                "close": 104.0,
                "volume": 1000000,
                "source": "test",
            }
        ]
    )