"""Client for the GIOŚ air-quality REST API, version v1.

Endpoints and response fields follow the official resource descriptions published by
GIOŚ in the open-data portal (dane.gov.pl, dataset 313) and the API page
https://powietrze.gios.gov.pl/pjp/content/api. The legacy ``/pjp-api/rest/...``
endpoints were withdrawn on 2025-06-30.

Every list endpoint is paginated (``page`` from 0, ``size`` up to 500) and wraps the
records in a single Polish-named list key next to ``links``/``meta``/``totalPages``.
The key name is not hard-coded: :func:`extract_records` picks the list of objects.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

from .config import find_field, normalize_text
from .http import HttpClient

log = logging.getLogger(__name__)

NON_DATA_KEYS = {"links", "meta", "totalpages", "page", "size"}

# Documented field names (Polish, as returned by the API).
F_SENSOR_CODE = "Kod stanowiska"
F_DATE = "Data"
F_VALUE = "Wartość"
F_POLLUTANT_CODE = "Wskaźnik - kod"
F_SENSOR_ID = "Identyfikator stanowiska"
F_STATION_ID = "Identyfikator stacji"


def extract_records(payload: Any) -> list[dict[str, Any]]:
    """Return the list of records from a GIOŚ response, whatever its wrapper key."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    candidates = {
        key: value
        for key, value in payload.items()
        if normalize_text(key) not in NON_DATA_KEYS
        and isinstance(value, list)
        and (not value or isinstance(value[0], dict))
    }
    if not candidates:
        return []
    if len(candidates) > 1:
        log.warning("Several list keys in response (%s); using the longest", list(candidates))
    return max(candidates.values(), key=len)


def total_pages(payload: Any) -> int | None:
    if isinstance(payload, dict):
        value = find_field(payload, "totalpages")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    return None


class GiosClient:
    def __init__(self, http: HttpClient, base_url: str, page_size: int = 500,
                 archive_window_days: int = 366, archive_date_format: str = "%Y-%m-%d %H:%M"):
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.page_size = page_size
        self.archive_window_days = archive_window_days
        self.archive_date_format = archive_date_format

    # -- generic -------------------------------------------------------------------------
    def paginate(self, path: str, params: dict[str, Any] | None = None,
                 group: str = "metadata") -> Iterator[list[dict[str, Any]]]:
        """Yield the records of each page until the last page is reached."""
        page = 0
        while True:
            query = {**(params or {}), "page": page, "size": self.page_size}
            payload = self.http.get_json(f"{self.base_url}/{path.lstrip('/')}", query, group)
            records = extract_records(payload)
            yield records
            pages = total_pages(payload)
            page += 1
            if pages is not None:
                if page >= pages:
                    break
            elif len(records) < self.page_size:
                break

    def fetch_all(self, path: str, params: dict[str, Any] | None = None,
                  group: str = "metadata") -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for records in self.paginate(path, params, group):
            out.extend(records)
        return out

    # -- metadata ------------------------------------------------------------------------
    def stations(self) -> list[dict[str, Any]]:
        return self.fetch_all("station/findAll", group="metadata")

    def station_metadata(self, city: str) -> list[dict[str, Any]]:
        return self.fetch_all("metadata/stations", {"filter[miejscowosc]": city}, group="metadata")

    def sensors(self, station_id: int) -> list[dict[str, Any]]:
        return self.fetch_all(f"station/sensors/{station_id}", group="metadata")

    def sensor_metadata(self, station_code: str) -> list[dict[str, Any]]:
        return self.fetch_all("metadata/sensors", {"filter[kod-stacji]": station_code}, group="metadata")

    # -- measurements --------------------------------------------------------------------
    def current_data(self, sensor_id: int) -> list[dict[str, Any]]:
        """Hourly values from the latest full hour back to ~3 days (unverified)."""
        return self.fetch_all(f"data/getData/{sensor_id}", group="current")

    def archive_windows(self, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        """Split [start, end] into windows accepted by archivalData/getDataBySensor."""
        windows = []
        step = timedelta(days=self.archive_window_days) - timedelta(hours=1)
        cursor = start
        while cursor <= end:
            window_end = min(cursor + step, end)
            windows.append((cursor, window_end))
            cursor = window_end + timedelta(hours=1)
        return windows

    def archive_by_sensor(self, sensor_id: int, date_from: datetime, date_to: datetime) -> list[dict]:
        params = {
            "dateFrom": date_from.strftime(self.archive_date_format),
            "dateTo": date_to.strftime(self.archive_date_format),
        }
        return self.fetch_all(f"archivalData/getDataBySensor/{sensor_id}", params, group="archive")


def filter_city_stations(stations: list[dict[str, Any]], city: str) -> list[dict[str, Any]]:
    """Keep stations located in ``city`` (field name of the city is matched loosely)."""
    wanted = normalize_text(city)
    out = []
    for station in stations:
        value = (find_field(station, "nazwa", "miasta") or find_field(station, "miejscowosc")
                 or find_field(station, "miasto") or find_field(station, "nazwa", "stacji") or "")
        text = normalize_text(value)
        if text == wanted or text.startswith(wanted + ",") or text.startswith(wanted + " "):
            out.append(station)
    return out


def station_id_of(station: dict[str, Any]) -> int | None:
    value = station.get(F_STATION_ID) or find_field(station, "identyfikator", "stacji") \
        or station.get("id")
    return int(value) if value is not None else None


def station_code_of(station: dict[str, Any]) -> str | None:
    return station.get("Kod stacji") or find_field(station, "kod", "stacji")
