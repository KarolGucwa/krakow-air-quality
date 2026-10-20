"""Command line entry point: ``aq <command>`` (or ``python -m aq_pipeline``)."""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from . import extract, sample_data
from .config import REPO_ROOT, load_settings
from .export_marts import export


def _date(text: str) -> date:
    return date.fromisoformat(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aq", description="Kraków air-quality pipeline")
    parser.add_argument("--config", type=Path, default=None, help="path to pipeline.yml")
    parser.add_argument("--raw-dir", type=Path, default=None, help="override raw_dir from config")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("daily", help="metadata (weekly) + last 3 days of measurements + recent weather")
    p.add_argument("--force-metadata", action="store_true")

    p = sub.add_parser("refresh-metadata", help="download station and sensor lists")
    p.add_argument("--force", action="store_true", default=True)

    yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
    p = sub.add_parser("backfill-gios", help="archival measurements via API (2 req/min, resumable)")
    p.add_argument("--start", type=_date, required=True)
    p.add_argument("--end", type=_date, default=yesterday)
    p.add_argument("--max-minutes", type=float, default=None, help="stop cleanly after N minutes")
    p.add_argument("--sensor-id", type=int, action="append", default=None,
                   help="only this sensor (repeatable), e.g. to fill a gap in the yearly packages")

    p = sub.add_parser("load-archive-files", help="parse yearly GIOŚ zip/xlsx packages")
    p.add_argument("--path", type=Path, default=REPO_ROOT / "data" / "landing" / "gios_archive")

    p = sub.add_parser("backfill-weather", help="Open-Meteo reanalysis for a date range")
    p.add_argument("--start", type=_date, required=True)
    p.add_argument("--end", type=_date, default=yesterday - timedelta(days=5))

    p = sub.add_parser("generate-sample", help="write a synthetic raw layer (offline demo / CI)")
    p.add_argument("--start", type=_date, default=date(2015, 1, 1))
    p.add_argument("--end", type=_date, default=None)
    p.add_argument("--seed", type=int, default=42)

    p = sub.add_parser("export-marts", help="copy dbt marts from DuckDB to Parquet for the dashboard")
    p.add_argument("--warehouse", type=Path, default=REPO_ROOT / "warehouse" / "krakow_air.duckdb")
    p.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "marts")
    p.add_argument("--data-mode", choices=["real", "synthetic"], default="real")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings(args.config, args.raw_dir)

    if args.command == "daily":
        extract.daily(settings, force_metadata=args.force_metadata)
    elif args.command == "refresh-metadata":
        gios, _ = extract.make_clients(settings)
        extract.refresh_metadata(settings, gios, force=True)
    elif args.command == "backfill-gios":
        gios, _ = extract.make_clients(settings)
        extract.backfill_gios_api(settings, gios, args.start, args.end, args.max_minutes, args.sensor_id)
    elif args.command == "load-archive-files":
        extract.load_archive_files(settings, args.path)
    elif args.command == "backfill-weather":
        _, meteo = extract.make_clients(settings)
        extract.backfill_weather(settings, meteo, args.start, args.end)
    elif args.command == "generate-sample":
        # never write synthetic records into the real raw layer by accident
        target = args.raw_dir or REPO_ROOT / "data" / "sample" / "raw"
        counts = sample_data.generate(Path(target), args.start, args.end, args.seed)
        for table, n in counts.items():
            logging.info("%-28s %10d records", table, n)
    elif args.command == "export-marts":
        export(args.warehouse, args.out, args.data_mode)


if __name__ == "__main__":
    main()
