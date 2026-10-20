"""Extraction jobs: each one fetches data and appends a batch to the raw layer."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Any

import pandas as pd

from . import raw_store
from .config import Settings, normalize_text
from .gios import (
    F_POLLUTANT_CODE,
    F_SENSOR_ID,
    GiosClient,
    filter_city_stations,
    station_code_of,
    station_id_of,
)
from .gios_archive_files import parse_archive
from .http import ApiError, HttpClient
from .openmeteo import OpenMeteoClient, year_chunks

log = logging.getLogger(__name__)

# GIOŚ answers 400 with this code for manual (24-hour, laboratory) sensors: their results
# are published months later and only daily, so the hourly pipeline skips them.
MANUAL_SENSOR_ERROR = "API-ERR-100003"


def make_clients(settings: Settings) -> tuple[GiosClient, OpenMeteoClient]:
    limits = {**settings.gios["rate_limits_per_min"], "openmeteo": 60}
    http = HttpClient(limits, timeout_s=settings.gios.get("timeout_s", 60))
    gios = GiosClient(
        http,
        settings.gios["base_url"],
        page_size=settings.gios["page_size"],
        archive_window_days=settings.gios["archive_window_days"],
        archive_date_format=settings.gios["archive_date_format"],
    )
    return gios, OpenMeteoClient(http, settings.weather)


# ---------------------------------------------------------------------------- metadata
def refresh_metadata(settings: Settings, gios: GiosClient, force: bool = False) -> None:
    """Download station and sensor lists for the configured city (at most weekly)."""
    raw_dir = settings.raw_dir
    last = raw_store.latest_ingestion("gios_sensors", raw_dir)
    max_age = timedelta(days=settings.gios["metadata_refresh_days"])
    if not force and last and datetime.now(UTC) - last < max_age:
        log.info("Metadata is fresh (last refresh %s), skipping", last)
        return

    batch = raw_store.new_batch_id("metadata")
    now = datetime.now(UTC)
    common = {"raw_dir": raw_dir}

    stations = filter_city_stations(gios.stations(), settings.city)
    if not stations:
        raise RuntimeError(f"No GIOŚ stations found for city {settings.city!r}")
    raw_store.write_records(stations, "gios_stations", source_system="gios_api",
                            endpoint="station/findAll", request_params={"city": settings.city},
                            ingested_at=now, batch_id=batch, **common)

    meta = gios.station_metadata(settings.city)
    # Guard against an ignored server-side filter (would mean ~300 stations at 2 req/min).
    meta = filter_city_stations(meta, settings.city) or meta
    raw_store.write_records(meta, "gios_station_metadata", source_system="gios_api",
                            endpoint="metadata/stations",
                            request_params={"filter[miejscowosc]": settings.city},
                            ingested_at=now, batch_id=batch, **common)

    sensors: list[dict[str, Any]] = []
    for station in stations:
        sid = station_id_of(station)
        if sid is None:
            log.warning("Station without id skipped: %s", station)
            continue
        for sensor in gios.sensors(sid):
            sensor.setdefault("Identyfikator stacji", sid)
            sensors.append(sensor)
    raw_store.write_records(sensors, "gios_sensors", source_system="gios_api",
                            endpoint="station/sensors/{stationId}",
                            request_params={"station_ids": [station_id_of(s) for s in stations]},
                            ingested_at=now, batch_id=batch, **common)

    codes = sorted({c for c in (station_code_of(s) for s in meta) if c})
    sensor_meta: list[dict[str, Any]] = []
    for code in codes:
        sensor_meta.extend(gios.sensor_metadata(code))
    raw_store.write_records(sensor_meta, "gios_sensor_metadata", source_system="gios_api",
                            endpoint="metadata/sensors", request_params={"station_codes": codes},
                            ingested_at=now, batch_id=batch, **common)


def configured_sensors(settings: Settings) -> list[dict[str, Any]]:
    """Sensors (numeric id + pollutant) from the latest metadata batch, filtered by pollutant."""
    wanted = {normalize_text(p) for p in settings.pollutants}
    sensors = raw_store.latest_batch_records("gios_sensors", settings.raw_dir)
    out = []
    for sensor in sensors:
        code = sensor.get(F_POLLUTANT_CODE) or ""
        if normalize_text(code) in wanted and sensor.get(F_SENSOR_ID) is not None:
            out.append({"sensor_id": int(sensor[F_SENSOR_ID]), "pollutant": code,
                        "station_id": sensor.get("Identyfikator stacji")})
    if not out:
        raise RuntimeError("No sensors in raw metadata. Run `aq refresh-metadata` first.")
    return out


def hourly_sensors(settings: Settings, gios: GiosClient) -> list[dict[str, Any]]:
    """Configured sensors without the manual ones (one cheap current-data call each)."""
    out = []
    for sensor in configured_sensors(settings):
        try:
            gios.current_data(sensor["sensor_id"])
        except ApiError as exc:
            if exc.code != MANUAL_SENSOR_ERROR:
                raise
            log.info("Sensor %s is manual (no hourly data), skipped", sensor["sensor_id"])
            continue
        out.append(sensor)
    return out


# ------------------------------------------------------------------------ measurements
def extract_current(settings: Settings, gios: GiosClient) -> int:
    """Last ~3 days of hourly data for every configured sensor (one batch per run)."""
    now = datetime.now(UTC)
    batch = raw_store.new_batch_id("gios-current")
    frames = []
    for sensor in configured_sensors(settings):
        try:
            records = gios.current_data(sensor["sensor_id"])
        except ApiError as exc:
            if exc.code != MANUAL_SENSOR_ERROR:
                raise
            log.info("Sensor %s is manual (no hourly data), skipped", sensor["sensor_id"])
            continue
        frames.append(raw_store.build_frame(records, source_system="gios_api_current",
                                            endpoint="data/getData/{sensorId}", request_params=sensor,
                                            ingested_at=now, batch_id=batch))
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raw_store.write_frame(frame, "gios_measurements", settings.raw_dir)  # one file per daily run
    log.info("Current measurements: %d records", len(frame))
    return len(frame)


def _state_path(settings: Settings) -> Path:
    return settings.raw_dir / "_state" / "gios_archive_backfill.json"


def _load_state(settings: Settings) -> set[str]:
    path = _state_path(settings)
    return set(json.loads(path.read_text())) if path.exists() else set()


def _save_state(settings: Settings, done: set[str]) -> None:
    path = _state_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(done), indent=1))


def backfill_gios_api(settings: Settings, gios: GiosClient, start: date, end: date,
                      max_minutes: float | None = None, sensor_ids: list[int] | None = None) -> int:
    """Archival measurements per sensor in <=366-day windows.

    The service allows 2 requests/minute, so this is slow (hours for a decade). It is
    resumable: completed (sensor, window) pairs are recorded in data/raw/_state and
    skipped on the next run; ``max_minutes`` stops cleanly before a CI timeout.
    For many years of history the yearly zip packages (``load-archive-files``) are faster;
    ``sensor_ids`` limits the run to a few sensors, e.g. to fill a gap in those packages.
    """
    started = time.monotonic()
    done = _load_state(settings)
    total = 0
    windows = gios.archive_windows(datetime.combine(start, dtime(0, 0)),
                                   datetime.combine(end, dtime(23, 0)))
    sensors = hourly_sensors(settings, gios)
    if sensor_ids:
        sensors = [s for s in sensors if s["sensor_id"] in sensor_ids]
    for sensor in sensors:
        for w_from, w_to in windows:
            key = f"{sensor['sensor_id']}|{w_from:%Y-%m-%d}|{w_to:%Y-%m-%d}"
            if key in done:
                continue
            if max_minutes and (time.monotonic() - started) / 60 > max_minutes:
                log.info("Time budget reached; %d records written, resume later", total)
                return total
            records = gios.archive_by_sensor(sensor["sensor_id"], w_from, w_to)
            raw_store.write_records(records, "gios_measurements", raw_dir=settings.raw_dir,
                                    source_system="gios_api_archive",
                                    endpoint="archivalData/getDataBySensor/{idSensor}",
                                    request_params={**sensor, "dateFrom": str(w_from), "dateTo": str(w_to)},
                                    batch_id=raw_store.new_batch_id(f"gios-archive-s{sensor['sensor_id']}"))
            done.add(key)
            _save_state(settings, done)
            total += len(records)
    log.info("Archive backfill complete: %d records", total)
    return total


def load_archive_files(settings: Settings, path: Path) -> int:
    prefixes = settings.gios.get("archive_station_code_prefixes") or None
    total = 0
    for file_name, records in parse_archive(path, settings.pollutants, prefixes):
        raw_store.write_records(records, "gios_measurements", raw_dir=settings.raw_dir,
                                source_system="gios_archive_file", endpoint="bank-danych-pomiarowych",
                                request_params={"file": file_name},
                                batch_id=raw_store.new_batch_id(f"gios-file-{Path(file_name).stem}"))
        total += len(records)
    log.info("Archive files: %d records", total)
    return total


# ----------------------------------------------------------------------------- weather
def extract_weather_recent(settings: Settings, meteo: OpenMeteoClient) -> int:
    """Forecast-model past days plus the newest available reanalysis days."""
    now = datetime.now(UTC)
    total = 0
    records, params = meteo.recent(settings.weather["forecast_past_days"])
    raw_store.write_records(records, "openmeteo_weather_hourly", raw_dir=settings.raw_dir,
                            source_system="openmeteo_forecast", endpoint="v1/forecast",
                            request_params=params, ingested_at=now)
    total += len(records)

    lag = settings.weather["archive_lag_days"]
    today = now.date()
    records, params = meteo.archive(today - timedelta(days=lag + 8), today - timedelta(days=lag))
    raw_store.write_records(records, "openmeteo_weather_hourly", raw_dir=settings.raw_dir,
                            source_system="openmeteo_archive", endpoint="v1/archive",
                            request_params=params, ingested_at=now)
    return total + len(records)


def backfill_weather(settings: Settings, meteo: OpenMeteoClient, start: date, end: date) -> int:
    total = 0
    for c_start, c_end in year_chunks(start, end):
        records, params = meteo.archive(c_start, c_end)
        raw_store.write_records(records, "openmeteo_weather_hourly", raw_dir=settings.raw_dir,
                                source_system="openmeteo_archive", endpoint="v1/archive",
                                request_params=params,
                                batch_id=raw_store.new_batch_id(f"weather-{c_start.year}"))
        total += len(records)
    return total


def daily(settings: Settings, force_metadata: bool = False) -> None:
    gios, meteo = make_clients(settings)
    refresh_metadata(settings, gios, force=force_metadata)
    extract_current(settings, gios)
    extract_weather_recent(settings, meteo)
