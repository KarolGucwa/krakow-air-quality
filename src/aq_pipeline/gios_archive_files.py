"""Parser for GIOŚ yearly archive packages ("Bank danych pomiarowych").

https://powietrze.gios.gov.pl/pjp/archives publishes one zip per year ("Wyniki pomiarów
z <rok> roku") with Excel workbooks per pollutant and averaging period, e.g.
``2019_PM10_1g.xlsx``. Each sheet is *wide*: a few header rows (``Kod stacji``,
``Wskaźnik``, ``Czas uśredniania``, optionally ``Kod stanowiska``, ``Jednostka``, ``Nr``)
followed by one row per hour (timestamp in the first column, CET) and one column
per station.

Layouts differ slightly between years, so the parser does not assume fixed row
numbers: header rows are recognised by their label in the first column and data rows
by a parseable timestamp in the first column. Output records use the same field names
as the API archival service, so all sources share one staging model.

Download the zips manually into ``data/landing/gios_archive/`` and run
``aq load-archive-files`` (the files are large and not meant for the repository).
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pandas as pd

from .config import normalize_text

log = logging.getLogger(__name__)

FILE_PATTERN = re.compile(r"(?P<year>\d{4})_(?P<pollutant>[A-Za-z0-9.]+?)_(?P<avg>\d+g)\.xlsx?$",
                          re.IGNORECASE)
POLLUTANT_ALIASES = {"pm25": "PM2.5", "pm2.5": "PM2.5", "pm10": "PM10"}
HEADER_LABELS = {
    "kod stacji": "station_code",
    "kod stanowiska": "sensor_code",
    "wskaznik": "pollutant",
    "czas usredniania": "averaging",
    "jednostka": "unit",
    "nr": "nr",
}


def canonical_pollutant(token: str) -> str:
    return POLLUTANT_ALIASES.get(token.lower(), token.upper())


def parse_filename(name: str) -> dict[str, str] | None:
    match = FILE_PATTERN.search(Path(name).name)
    if not match:
        return None
    return {
        "year": match["year"],
        "pollutant": canonical_pollutant(match["pollutant"]),
        "averaging": match["avg"].lower(),
    }


def _to_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_sheet(frame: pd.DataFrame, pollutant: str, averaging: str, source_file: str,
                station_prefixes: list[str] | None = None) -> list[dict[str, Any]]:
    """Convert one wide sheet (read with header=None) into long API-shaped records."""
    headers: dict[str, list[Any]] = {}
    data_start = None
    for idx in range(len(frame)):
        first = frame.iat[idx, 0]
        label = normalize_text(first) if isinstance(first, str) else ""
        if label in HEADER_LABELS:
            headers[HEADER_LABELS[label]] = list(frame.iloc[idx, 1:])
            continue
        ts = pd.to_datetime(first, errors="coerce") if first is not None else pd.NaT
        if pd.notna(ts) and "station_code" in headers:
            data_start = idx
            break
    if data_start is None:
        log.warning("%s: no 'Kod stacji' header / data rows found, skipped", source_file)
        return []

    station_codes = [str(c).strip() if c is not None and not pd.isna(c) else None
                     for c in headers["station_code"]]
    sensor_codes = headers.get("sensor_code") or [None] * len(station_codes)

    keep_cols = []
    for col, code in enumerate(station_codes):
        if not code:
            continue
        if station_prefixes and not any(code.startswith(p) for p in station_prefixes):
            continue
        sensor = sensor_codes[col] if col < len(sensor_codes) else None
        if sensor is None or (isinstance(sensor, float) and pd.isna(sensor)) or not str(sensor).strip():
            sensor = f"{code}-{pollutant}-{averaging}"
        keep_cols.append((col + 1, code, str(sensor).strip()))

    records: list[dict[str, Any]] = []
    body = frame.iloc[data_start:]
    # Excel stores the hours as floats that drift by up to a minute over a year
    # ("2015-12-31 23:00:43.785"), so snap them to the nearest full hour.
    timestamps = pd.to_datetime(body.iloc[:, 0], errors="coerce").dt.round("h")
    for frame_col, station_code, sensor_code in keep_cols:
        values = body.iloc[:, frame_col]
        for ts, raw in zip(timestamps, values, strict=True):
            if pd.isna(ts):
                continue
            value = _to_float(raw)
            if value is None:
                continue  # empty cell = no measurement; missing hours are derived in dbt
            records.append({
                "Kod stanowiska": sensor_code,
                "Kod stacji": station_code,
                "Data": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "Wartość": value,
                "Plik": source_file,
            })
    return records


def iter_workbooks(path: Path) -> Iterator[tuple[str, bytes]]:
    """Yield (file name, bytes) for every xlsx file in a folder, zip or single file."""
    path = Path(path)
    if path.is_dir():
        for child in sorted(path.iterdir()):
            yield from iter_workbooks(child)
    elif path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            for name in sorted(zf.namelist()):
                if name.lower().endswith((".xlsx", ".xls")):
                    yield name, zf.read(name)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        yield path.name, path.read_bytes()


def parse_archive(path: Path, pollutants: list[str], station_prefixes: list[str] | None = None,
                  averaging: str = "1g") -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Yield (file name, records) for matching workbooks found under ``path``."""
    wanted = {canonical_pollutant(p) for p in pollutants}
    for name, content in iter_workbooks(path):
        meta = parse_filename(name)
        if not meta or meta["pollutant"] not in wanted or meta["averaging"] != averaging:
            continue
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None, dtype=object)
        records: list[dict[str, Any]] = []
        for sheet in sheets.values():
            records.extend(parse_sheet(sheet, meta["pollutant"], meta["averaging"], Path(name).name,
                                       station_prefixes))
        log.info("%s: %d records for stations %s", name, len(records), station_prefixes)
        yield Path(name).name, records
