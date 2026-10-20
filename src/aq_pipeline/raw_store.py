"""Raw (bronze) layer: append-only, partitioned Parquet files.

Every API record is stored *as received* in ``record_json`` together with load metadata.
Parsing happens later in dbt staging models (schema-on-read), so a changed or added
field in the source never breaks ingestion, and history can always be re-parsed.

Layout::

    data/raw/<table>/ingestion_date=YYYY-MM-DD/<batch_id>.parquet
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

log = logging.getLogger(__name__)

RAW_COLUMNS = [
    "record_json",
    "source_system",
    "endpoint",
    "request_params",
    "ingested_at",
    "batch_id",
]

TABLES = {
    "gios_stations",           # station/findAll (numeric ids used for later requests)
    "gios_station_metadata",   # metadata/stations (codes, coordinates, station type)
    "gios_sensors",            # station/sensors/{stationId}
    "gios_sensor_metadata",    # metadata/sensors (sensor code -> station code, averaging)
    "gios_measurements",       # current + archival measurements from API and archive files
    "openmeteo_weather_hourly",
}


def new_batch_id(prefix: str = "batch") -> str:
    return f"{prefix}-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"


def build_frame(
    records: Iterable[dict[str, Any]],
    *,
    source_system: str,
    endpoint: str,
    request_params: dict[str, Any] | None = None,
    ingested_at: datetime | None = None,
    batch_id: str | None = None,
) -> pd.DataFrame:
    ingested_at = (ingested_at or datetime.now(UTC)).astimezone(UTC).replace(tzinfo=None)
    params_json = json.dumps(request_params or {}, ensure_ascii=False, sort_keys=True)
    rows = [json.dumps(r, ensure_ascii=False, default=str) for r in records]
    frame = pd.DataFrame({"record_json": rows})
    frame["source_system"] = source_system
    frame["endpoint"] = endpoint
    frame["request_params"] = params_json
    frame["ingested_at"] = pd.Timestamp(ingested_at)
    frame["batch_id"] = batch_id or new_batch_id()
    return frame[RAW_COLUMNS]


def write_frame(frame: pd.DataFrame, table: str, raw_dir: Path) -> Path | None:
    """Write one batch file. Returns the path, or None for an empty batch."""
    if table not in TABLES:
        raise ValueError(f"Unknown raw table {table!r}; expected one of {sorted(TABLES)}")
    if frame.empty:
        log.info("%s: nothing to write", table)
        return None
    frame = frame.copy()
    frame["ingested_at"] = pd.to_datetime(frame["ingested_at"]).astype("datetime64[us]")
    ingestion_date = frame["ingested_at"].iloc[0].date().isoformat()
    batch_id = frame["batch_id"].iloc[0]
    target = Path(raw_dir) / table / f"ingestion_date={ingestion_date}" / f"{batch_id}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    write_parquet(frame, target)
    log.info("%s: wrote %d records -> %s", table, len(frame), target)
    return target


def write_parquet(frame: pd.DataFrame, target: Path) -> None:
    """Parquet I/O goes through DuckDB, not pyarrow: pyarrow's native Parquet module is
    blocked on some Windows machines (Smart App Control), DuckDB's is not."""
    con = duckdb.connect()
    try:
        con.register("frame", frame)
        con.execute(f"copy frame to '{Path(target).as_posix()}' (format parquet, compression zstd)")
    finally:
        con.close()


def read_parquet(files: list[Path]) -> pd.DataFrame:
    paths = ", ".join(f"'{Path(f).as_posix()}'" for f in files)
    con = duckdb.connect()
    try:
        sql = f"select * from read_parquet([{paths}], union_by_name = true, hive_partitioning = false)"
        return con.execute(sql).df()
    finally:
        con.close()


def write_records(records: list[dict[str, Any]], table: str, raw_dir: Path, **meta: Any) -> Path | None:
    return write_frame(build_frame(records, **meta), table, raw_dir)


def read_table(table: str, raw_dir: Path) -> pd.DataFrame:
    """Read every batch of a raw table (empty frame if nothing was ingested yet)."""
    files = sorted((Path(raw_dir) / table).glob("ingestion_date=*/*.parquet"))
    if not files:
        return pd.DataFrame(columns=RAW_COLUMNS)
    return read_parquet(files)


def latest_ingestion(table: str, raw_dir: Path) -> datetime | None:
    frame = read_table(table, raw_dir)
    if frame.empty:
        return None
    return pd.to_datetime(frame["ingested_at"]).max().to_pydatetime().replace(tzinfo=UTC)


def latest_batch_records(table: str, raw_dir: Path) -> list[dict[str, Any]]:
    """Records (with parsed request params) from the most recent batch of a table."""
    frame = read_table(table, raw_dir)
    if frame.empty:
        return []
    frame = frame.sort_values("ingested_at")
    last = frame[frame["ingested_at"] == frame["ingested_at"].max()]
    out = []
    for rec, params in zip(last["record_json"], last["request_params"], strict=True):
        item = json.loads(rec)
        item["_request_params"] = json.loads(params)
        out.append(item)
    return out
