"""End-to-end test of the extraction jobs with a fake HTTP layer (no network).

Responses mimic the documented GIOŚ v1 and Open-Meteo shapes, including pagination
wrappers. The test checks that every raw table is written and can be read back.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from aq_pipeline import extract, raw_store
from aq_pipeline.config import load_settings
from aq_pipeline.gios import GiosClient
from aq_pipeline.http import ApiError, HttpClient
from aq_pipeline.openmeteo import OpenMeteoClient

from .conftest import FakeResponse

STATIONS = [
    {"Identyfikator stacji": 400, "Kod stacji": "MpKrakAlKras", "Nazwa stacji": "Kraków, Aleja Krasińskiego",
     "Nazwa miasta": "Kraków"},
    {"Identyfikator stacji": 999, "Kod stacji": "MpSkawinaSad", "Nazwa stacji": "Skawina, ul. Ogrodowa",
     "Nazwa miasta": "Skawina"},
]


def wrap(key: str, records: list[dict]) -> dict:
    return {"links": {"self": "x"}, "totalPages": 1, key: records}


def hourly_values(hours: int = 72) -> list[dict]:
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)  # local summer-ish
    return [{"Kod stanowiska": "MpKrakAlKras-PM10-1g",
             "Data": (now - timedelta(hours=h)).strftime("%Y-%m-%d %H:%M:%S"),
             "Wartość": None if h == 0 else 20.0 + h % 5} for h in range(hours)]


def fake_get_json(url: str, params: dict | None = None, group: str = "default"):
    if url.endswith("/station/findAll"):
        return wrap("Lista stacji pomiarowych", STATIONS)
    if url.endswith("/metadata/stations"):
        return wrap("Lista metadanych stacji pomiarowych", [
            {"Kod stacji": "MpKrakAlKras", "Nazwa stacji": "Kraków, Aleja Krasińskiego", "Typ stacji": "komunikacyjna",
             "Miejscowość": "Kraków", "WGS84 φ N": "50.057678", "WGS84 λ E": "19.926189"}])
    if "/station/sensors/" in url:
        return wrap("Lista stanowisk pomiarowych dla podanej stacji", [
            {"Identyfikator stanowiska": 2770, "Identyfikator stacji": 400, "Wskaźnik - kod": "PM10"},
            {"Identyfikator stanowiska": 2771, "Identyfikator stacji": 400, "Wskaźnik - kod": "NO2"}])
    if url.endswith("/metadata/sensors"):
        return wrap("Lista metadanych stanowisk pomiarowych", [
            {"Kod stanowiska": "MpKrakAlKras-PM10-1g", "Kod stacji": "MpKrakAlKras", "Wskaźnik - kod": "PM10"}])
    if "/data/getData/" in url:
        return wrap("Lista danych pomiarowych", hourly_values())
    if "/archivalData/getDataBySensor/" in url:
        return wrap("Lista archiwalnych wyników pomiarów", hourly_values(24))
    if "open-meteo" in url:
        start = datetime(2026, 1, 1)
        times = [(start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in range(48)]
        return {"hourly": {"time": times, "temperature_2m": [1.5] * 48, "wind_speed_10m": [2.0] * 48}}
    raise AssertionError(f"unexpected URL {url}")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    settings = load_settings(raw_dir=tmp_path)
    http = HttpClient({}, sleep=lambda s: None)
    monkeypatch.setattr(http, "get_json", fake_get_json)
    gios = GiosClient(http, settings.gios["base_url"], page_size=500)
    meteo = OpenMeteoClient(http, settings.weather)
    return settings, gios, meteo, tmp_path


def test_daily_flow_writes_every_raw_table(setup):
    settings, gios, meteo, raw_dir = setup
    extract.refresh_metadata(settings, gios)
    extract.extract_current(settings, gios)
    extract.extract_weather_recent(settings, meteo)

    stations = raw_store.read_table("gios_stations", raw_dir)
    assert len(stations) == 1  # Skawina filtered out
    sensors = extract.configured_sensors(settings)
    assert [s["sensor_id"] for s in sensors] == [2770]  # NO2 filtered out
    measurements = raw_store.read_table("gios_measurements", raw_dir)
    assert len(measurements) == 72
    assert set(measurements["source_system"]) == {"gios_api_current"}
    weather = raw_store.read_table("openmeteo_weather_hourly", raw_dir)
    assert set(weather["source_system"]) == {"openmeteo_forecast", "openmeteo_archive"}
    assert '"location_id": "krakow_center"' in weather["request_params"].iloc[0]


def test_metadata_refresh_is_skipped_when_fresh(setup):
    settings, gios, _, raw_dir = setup
    extract.refresh_metadata(settings, gios)
    files_before = sorted(raw_dir.rglob("*.parquet"))
    extract.refresh_metadata(settings, gios)
    assert sorted(raw_dir.rglob("*.parquet")) == files_before


def test_archive_backfill_is_resumable(setup):
    settings, gios, _, raw_dir = setup
    extract.refresh_metadata(settings, gios)
    first = extract.backfill_gios_api(settings, gios, date(2024, 1, 1), date(2025, 6, 30))
    assert first == 2 * 24  # two windows for one PM10 sensor
    again = extract.backfill_gios_api(settings, gios, date(2024, 1, 1), date(2025, 6, 30))
    assert again == 0  # both windows recorded in the state file
    assert (raw_dir / "_state" / "gios_archive_backfill.json").exists()


def test_manual_sensors_are_skipped(setup, monkeypatch):
    """GIOŚ answers 400 / API-ERR-100003 for manual (24-hour) sensors."""
    settings, gios, _, raw_dir = setup

    def with_manual_sensor(url: str, params: dict | None = None, group: str = "default"):
        if "/station/sensors/" in url:
            return wrap("Lista stanowisk pomiarowych dla podanej stacji", [
                {"Identyfikator stanowiska": 2770, "Identyfikator stacji": 400, "Wskaźnik - kod": "PM10"},
                {"Identyfikator stanowiska": 2772, "Identyfikator stacji": 400, "Wskaźnik - kod": "PM10"}])
        if url.endswith("/2772"):
            raise ApiError(extract.MANUAL_SENSOR_ERROR, "manual sensor", FakeResponse({}, status=400))
        return fake_get_json(url, params, group)

    monkeypatch.setattr(gios.http, "get_json", with_manual_sensor)
    extract.refresh_metadata(settings, gios)
    assert extract.extract_current(settings, gios) == 72
    assert extract.backfill_gios_api(settings, gios, date(2025, 1, 1), date(2025, 1, 31)) == 24


def test_archive_backfill_can_be_limited_to_sensors(setup):
    settings, gios, _, raw_dir = setup
    extract.refresh_metadata(settings, gios)
    assert extract.backfill_gios_api(settings, gios, date(2025, 1, 1), date(2025, 1, 31), sensor_ids=[1]) == 0
    assert extract.backfill_gios_api(settings, gios, date(2025, 1, 1), date(2025, 1, 31), sensor_ids=[2770]) == 24
