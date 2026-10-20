"""Export dbt marts from the DuckDB warehouse to Parquet for the dashboard.

The dashboard (local or Streamlit Community Cloud) reads only these small files, so it
needs neither the warehouse file nor dbt.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import duckdb

log = logging.getLogger(__name__)

EXPORT_SCHEMAS = ("marts", "dq", "analysis")
# Row-level tables stay in the warehouse: they are large and would bloat the git history
# of the daily commit. The dashboard only needs daily and aggregated marts.
EXCLUDE = {("marts", "fct_air_quality_hourly"), ("dq", "dq_rejected_measurements")}


def export(warehouse: Path, out_dir: Path, data_mode: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with duckdb.connect(str(warehouse), read_only=True) as con:
        tables = con.execute(
            "select table_schema, table_name from information_schema.tables "
            f"where table_schema in {EXPORT_SCHEMAS} order by 1, 2"
        ).fetchall()
        if not tables:
            raise RuntimeError(f"No mart tables in {warehouse}; run `dbt build` first")
        for schema, table in tables:
            if (schema, table) in EXCLUDE:
                continue
            target = out_dir / f"{schema}__{table}.parquet"
            con.execute(f'copy "{schema}"."{table}" to \'{target.as_posix()}\' (format parquet, compression zstd)')
            written.append(target)
            log.info("exported %s.%s -> %s", schema, table, target)
    meta = {"data_mode": data_mode, "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "tables": [p.name for p in written]}
    (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2))
    return written
