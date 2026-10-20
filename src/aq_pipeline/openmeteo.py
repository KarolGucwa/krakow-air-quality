"""Open-Meteo hourly weather: historical archive (reanalysis) and recent forecast-model past.

Responses are column-oriented (``hourly.time`` plus one array per variable). They are
flattened to one record per hour; values are kept exactly as returned. Timestamps are
requested in UTC (``timezone=GMT``).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .http import HttpClient


def flatten_hourly(payload: dict[str, Any]) -> list[dict[str, Any]]:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    variables = [k for k in hourly if k != "time"]
    records = []
    for i, ts in enumerate(times):
        rec = {"time": ts}
        for var in variables:
            values = hourly[var]
            rec[var] = values[i] if i < len(values) else None
        records.append(rec)
    return records


def year_chunks(start: date, end: date) -> list[tuple[date, date]]:
    chunks = []
    cursor = start
    while cursor <= end:
        chunk_end = min(date(cursor.year, 12, 31), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


class OpenMeteoClient:
    def __init__(self, http: HttpClient, settings: dict[str, Any]):
        self.http = http
        self.s = settings

    def _base_params(self) -> dict[str, Any]:
        return {
            "latitude": self.s["latitude"],
            "longitude": self.s["longitude"],
            "hourly": ",".join(self.s["hourly_variables"]),
            "wind_speed_unit": self.s.get("wind_speed_unit", "ms"),
            "timezone": "GMT",
        }

    def archive(self, start: date, end: date) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        params = {**self._base_params(), "start_date": start.isoformat(), "end_date": end.isoformat()}
        payload = self.http.get_json(self.s["archive_url"], params, group="openmeteo")
        return flatten_hourly(payload), {**params, "location_id": self.s["location_id"]}

    def recent(self, past_days: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        params = {**self._base_params(), "past_days": past_days, "forecast_days": 1}
        payload = self.http.get_json(self.s["forecast_url"], params, group="openmeteo")
        return flatten_hourly(payload), {**params, "location_id": self.s["location_id"]}
