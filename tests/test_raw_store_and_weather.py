import json
from datetime import UTC, date, datetime

import pandas as pd

from aq_pipeline import raw_store
from aq_pipeline.openmeteo import flatten_hourly, year_chunks


def test_write_and_read_partitioned_batch(tmp_path):
    ts = datetime(2026, 10, 1, 5, 0, tzinfo=UTC)
    path = raw_store.write_records(
        [{"Kod stanowiska": "MpKrakAlKras-PM10-1g", "Wartość": 12.5}], "gios_measurements", tmp_path,
        source_system="gios_api_current", endpoint="data/getData/{sensorId}",
        request_params={"sensor_id": 1}, ingested_at=ts, batch_id="b1")
    assert path == tmp_path / "gios_measurements" / "ingestion_date=2026-10-01" / "b1.parquet"
    frame = raw_store.read_table("gios_measurements", tmp_path)
    assert list(frame.columns) == raw_store.RAW_COLUMNS
    record = json.loads(frame.loc[0, "record_json"])
    assert record["Wartość"] == 12.5  # stored as received, Polish keys intact
    assert pd.Timestamp(frame.loc[0, "ingested_at"]) == pd.Timestamp("2026-10-01 05:00")
    assert raw_store.latest_ingestion("gios_measurements", tmp_path) == ts


def test_empty_batch_writes_nothing(tmp_path):
    assert raw_store.write_records([], "gios_sensors", tmp_path, source_system="x", endpoint="y") is None
    assert raw_store.read_table("gios_sensors", tmp_path).empty


def test_latest_batch_records(tmp_path):
    for i, day in enumerate([1, 3]):
        raw_store.write_records([{"Identyfikator stanowiska": i}], "gios_sensors", tmp_path,
                                source_system="gios_api", endpoint="e", request_params={"run": i},
                                ingested_at=datetime(2026, 10, day, tzinfo=UTC), batch_id=f"b{i}")
    latest = raw_store.latest_batch_records("gios_sensors", tmp_path)
    assert latest == [{"Identyfikator stanowiska": 1, "_request_params": {"run": 1}}]


def test_flatten_open_meteo():
    payload = {"hourly": {"time": ["2024-01-01T00:00", "2024-01-01T01:00"],
                          "temperature_2m": [-1.5, -2.0], "precipitation": [0.0, None]}}
    assert flatten_hourly(payload) == [
        {"time": "2024-01-01T00:00", "temperature_2m": -1.5, "precipitation": 0.0},
        {"time": "2024-01-01T01:00", "temperature_2m": -2.0, "precipitation": None},
    ]
    assert flatten_hourly({}) == []


def test_year_chunks():
    assert year_chunks(date(2018, 6, 1), date(2020, 2, 1)) == [
        (date(2018, 6, 1), date(2018, 12, 31)),
        (date(2019, 1, 1), date(2019, 12, 31)),
        (date(2020, 1, 1), date(2020, 2, 1)),
    ]
