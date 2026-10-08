from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import duckdb
import pandas as pd

from marketlens.config import DATA_DIR
from marketlens.intraday.models import IntradayCandle


class ParquetPartitioner:
    """
    High-Performance Partitioned Parquet Storage Engine with native DuckDB integration.

    Invariants:
    1. Zero Vendor Lock-in: Historical and intraday candles are saved in standard, open
       Apache Parquet files partitioned by market, symbol, timeframe, and year:
       'data/parquet/{market}/{symbol}/{timeframe}/{year}.parquet'
    2. Blazing Speed: DuckDB executes analytical vector queries directly against the
       partitioned Parquet files without requiring intermediate imports.
    3. Scalability: Handles multi-year 5-minute and 1-minute datasets (millions of rows)
       with high columnar compression.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or (DATA_DIR / "parquet")
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def _get_partition_path(
        self,
        market: str,
        symbol: str,
        timeframe: str,
        year: int,
    ) -> Path:
        clean_market = market.strip().lower()
        clean_sym = symbol.strip().upper().replace(" ", "_").replace("^", "")
        clean_tf = timeframe.strip().lower()
        folder = self._base_dir / clean_market / clean_sym / clean_tf
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{year}.parquet"

    def write_candles(
        self,
        market: str,
        symbol: str,
        timeframe: str,
        candles: Sequence[IntradayCandle],
    ) -> int:
        """
        Write or append a sequence of IntradayCandles to partitioned Parquet files.
        Deduplicates records by timestamp to ensure idempotency.
        """
        if not candles:
            return 0

        # Convert candles to DataFrame
        records = []
        for c in candles:
            # Normalize timestamp to datetime
            ts = c.timestamp
            if isinstance(ts, (int, float)):
                ts_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            elif isinstance(ts, str):
                ts_dt = pd.to_datetime(ts, utc=True).to_pydatetime()
            elif isinstance(ts, datetime):
                ts_dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            else:
                ts_dt = datetime.now(timezone.utc)

            records.append(
                {
                    "timestamp": ts_dt,
                    "open": float(c.open),
                    "high": float(c.high),
                    "low": float(c.low),
                    "close": float(c.close),
                    "volume": float(c.volume),
                    "year": ts_dt.year,
                }
            )

        df = pd.DataFrame(records)

        total_written = 0
        con = duckdb.connect()
        try:
            # Group by year and write partitioned files using DuckDB native Parquet
            for year, year_group in df.groupby("year"):
                parquet_path = self._get_partition_path(market, symbol, timeframe, int(year))
                to_write = year_group.drop(columns=["year"])
                sql_path = str(parquet_path).replace("\\", "/")

                if parquet_path.exists():
                    existing_df = con.execute(f"SELECT * FROM read_parquet('{sql_path}')").df()
                    combined = pd.concat([existing_df, to_write], ignore_index=True)
                    deduped = combined.drop_duplicates(subset=["timestamp"], keep="last")
                    deduped = deduped.sort_values(by="timestamp").reset_index(drop=True)
                    con.register("to_save", deduped)
                    con.execute(f"COPY to_save TO '{sql_path}' (FORMAT PARQUET)")
                    con.unregister("to_save")
                    total_written += len(deduped)
                else:
                    to_write = to_write.sort_values(by="timestamp").reset_index(drop=True)
                    con.register("to_save", to_write)
                    con.execute(f"COPY to_save TO '{sql_path}' (FORMAT PARQUET)")
                    con.unregister("to_save")
                    total_written += len(to_write)
        finally:
            con.close()

        return total_written

    def read_candles(
        self,
        market: str,
        symbol: str,
        timeframe: str,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[IntradayCandle]:
        """
        Read candles from partitioned Parquet files using DuckDB's vectorized reader.
        """
        clean_market = market.strip().lower()
        clean_sym = symbol.strip().upper().replace(" ", "_").replace("^", "")
        clean_tf = timeframe.strip().lower()
        pattern = self._base_dir / clean_market / clean_sym / clean_tf / "*.parquet"

        # Check if files exist
        glob_path = str(pattern).replace("\\", "/")
        con = duckdb.connect()
        try:
            query = f"SELECT * FROM read_parquet('{glob_path}') ORDER BY timestamp ASC"
            df = con.execute(query).df()
        except Exception:
            con.close()
            return []
        con.close()

        if df.empty:
            return []

        # Filter by year if specified
        if start_year is not None:
            df = df[df["timestamp"].dt.year >= start_year]
        if end_year is not None:
            df = df[df["timestamp"].dt.year <= end_year]

        candles: list[IntradayCandle] = []
        for _, row in df.iterrows():
            candles.append(
                IntradayCandle(
                    timestamp=row["timestamp"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
        return candles

    def query_parquet(
        self,
        sql_query: str,
    ) -> pd.DataFrame:
        """
        Execute an arbitrary DuckDB SQL query across Parquet files.
        """
        con = duckdb.connect()
        try:
            df = con.execute(sql_query).df()
        finally:
            con.close()
        return df

    def get_storage_stats(self) -> dict[str, Any]:
        """
        Calculate total storage utilization and metadata.
        """
        total_files = 0
        total_bytes = 0
        symbols_found = set()

        for root, _, files in os.walk(self._base_dir):
            for f in files:
                if f.endswith(".parquet"):
                    total_files += 1
                    fp = Path(root) / f
                    total_bytes += fp.stat().st_size
                    # symbol is second level from base_dir
                    rel = fp.relative_to(self._base_dir)
                    parts = rel.parts
                    if len(parts) >= 2:
                        symbols_found.add(parts[1])

        return {
            "total_files": total_files,
            "total_size_mb": round(total_bytes / (1024 * 1024), 3),
            "symbols_count": len(symbols_found),
            "symbols": sorted(list(symbols_found)),
            "storage_path": str(self._base_dir),
        }
