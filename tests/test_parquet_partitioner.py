from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pytest

from marketlens.intraday.models import IntradayCandle
from marketlens.storage import ParquetPartitioner


def test_parquet_partitioner_write_read_and_stats(tmp_path: Path) -> None:
    partitioner = ParquetPartitioner(base_dir=tmp_path)

    # 1. Create test candles across two different years (2025 and 2026)
    candles_2025 = [
        IntradayCandle(
            timestamp=datetime(2025, 12, 31, 9, 15 + i * 5, tzinfo=timezone.utc),
            open=100.0 + i,
            high=102.0 + i,
            low=99.0 + i,
            close=101.0 + i,
            volume=5000.0,
        )
        for i in range(5)
    ]

    candles_2026 = [
        IntradayCandle(
            timestamp=datetime(2026, 1, 1, 9, 15 + i * 5, tzinfo=timezone.utc),
            open=110.0 + i,
            high=112.0 + i,
            low=109.0 + i,
            close=111.0 + i,
            volume=6000.0,
        )
        for i in range(5)
    ]

    # Write both batches
    written_count = partitioner.write_candles(
        market="nse",
        symbol="NIFTY 50",
        timeframe="5m",
        candles=candles_2025 + candles_2026,
    )
    assert written_count == 10

    # 2. Verify physical directory structure
    nifty_folder = tmp_path / "nse" / "NIFTY_50" / "5m"
    assert (nifty_folder / "2025.parquet").exists()
    assert (nifty_folder / "2026.parquet").exists()

    # 3. Read all candles back using vectorized reader
    read_all = partitioner.read_candles(market="nse", symbol="NIFTY 50", timeframe="5m")
    assert len(read_all) == 10
    assert read_all[0].open == 100.0
    assert read_all[-1].close == 115.0

    # 4. Filter by start_year
    read_2026 = partitioner.read_candles(
        market="nse", symbol="NIFTY 50", timeframe="5m", start_year=2026
    )
    assert len(read_2026) == 5
    assert all(c.timestamp.year == 2026 for c in read_2026)

    # 5. Idempotent Deduplication: writing the same candles again doesn't duplicate
    re_written = partitioner.write_candles(
        market="nse", symbol="NIFTY 50", timeframe="5m", candles=candles_2026
    )
    assert re_written == 5
    read_after = partitioner.read_candles(market="nse", symbol="NIFTY 50", timeframe="5m")
    assert len(read_after) == 10  # Still 10, not 15!

    # 6. Direct DuckDB SQL query across Parquet
    glob_pattern = str(nifty_folder / "*.parquet").replace("\\", "/")
    sql = f"SELECT count(*) as cnt, avg(close) as avg_c FROM read_parquet('{glob_pattern}')"
    df = partitioner.query_parquet(sql)
    assert df["cnt"].iloc[0] == 10

    # 7. Storage statistics
    stats = partitioner.get_storage_stats()
    assert stats["total_files"] == 2
    assert stats["symbols_count"] == 1
    assert "NIFTY_50" in stats["symbols"]
    assert stats["total_size_mb"] > 0
