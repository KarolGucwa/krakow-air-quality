"""Synthetic raw data with exactly the shape of the real sources.

Purpose: run and test the whole pipeline offline (CI, demo, development) without
hitting rate-limited APIs. **These numbers are invented.** The dashboard shows a
"synthetic data" banner whenever marts were built from this generator.

What is simulated:

* weather: seasonal + diurnal temperature, synoptic variability, wind, rain, humidity;
* PM10/PM2.5 per station driven by heating demand, traffic (weekday/rush hours),
  dispersion (wind, rain) and noise; heating emissions inside Kraków decline slowly
  (stove-replacement programme) and drop at the solid-fuel ban on 2019-09-01, while
  emissions from outside the city (relevant at edge stations) decline only slowly;
* source mix as in production: yearly archive files (CET timestamps), API archival
  backfill for the current year, repeated daily current-API snapshots (local time),
  forecast and reanalysis weather;
* data-quality problems: outages, negative readings, isolated spikes, absurd values,
  nulls in the current API, overlapping sources.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import lfilter

from . import raw_store

BAN_DATE = pd.Timestamp("2019-09-01")


@dataclass(frozen=True)
class SyntheticStation:
    station_id: int
    code: str
    name: str
    street: str
    station_type: str
    lat: float
    lon: float
    heating: float        # relative residential-heating influence
    traffic: float        # relative traffic influence
    outside_share: float  # share of heating emissions coming from outside the city (no ban)
    industrial: float     # constant industrial contribution, µg/m³
    pm25: bool
    pm10_start: str = "2015-01-01"
    pm25_start: str = "2015-01-01"


STATIONS = [
    SyntheticStation(400, "MpKrakAlKras", "Kraków, Aleja Krasińskiego", "al. Krasińskiego",
                     "komunikacyjna", 50.0577, 19.9262, 1.00, 1.45, 0.10, 0.0, True),
    SyntheticStation(401, "MpKrakBujaka", "Kraków, ul. Bujaka", "ul. Bujaka", "tło",
                     50.0106, 19.9492, 0.95, 0.45, 0.15, 0.0, True),
    SyntheticStation(402, "MpKrakBulwar", "Kraków, ul. Bulwarowa", "ul. Bulwarowa", "przemysłowa",
                     50.0693, 20.0535, 1.00, 0.60, 0.20, 7.0, True),
    SyntheticStation(10435, "MpKrakDietla", "Kraków, ul. Dietla", "ul. Dietla", "komunikacyjna",
                     50.0574, 19.9460, 1.00, 1.25, 0.10, 0.0, True, pm25_start="2016-06-01"),
    SyntheticStation(10121, "MpKrakOsPias", "Kraków, os. Piastów", "os. Piastów", "tło",
                     50.0985, 20.0183, 0.95, 0.40, 0.20, 0.0, True, pm25_start="2018-03-01"),
    SyntheticStation(10123, "MpKrakSwoszo", "Kraków, ul. Swoszowice", "ul. Kąpielowa", "tło",
                     49.9914, 19.9368, 1.15, 0.20, 0.35, 0.0, False, pm10_start="2016-01-01"),
    SyntheticStation(10139, "MpKrakWadow", "Kraków, os. Wadów", "os. Wadów", "tło",
                     50.1006, 20.1226, 1.20, 0.30, 0.45, 0.0, False),
    SyntheticStation(10447, "MpKrakZloRog", "Kraków, ul. Złoty Róg", "ul. Złoty Róg", "tło",
                     50.0812, 19.8954, 1.00, 0.35, 0.20, 0.0, True, pm10_start="2017-01-01",
                     pm25_start="2017-01-01"),
]


def _ar1(rng: np.random.Generator, n: int, phi: float, sd: float) -> np.ndarray:
    """Stationary AR(1) series with marginal standard deviation ``sd``."""
    innov = rng.normal(0, sd * np.sqrt(1 - phi**2), n)
    return lfilter([1.0], [1.0, -phi], innov)


def _hours(start: date, end_exclusive: datetime) -> pd.DatetimeIndex:
    return pd.date_range(pd.Timestamp(start), pd.Timestamp(end_exclusive), freq="h", inclusive="left")


def simulate_weather(index: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    n = len(index)
    local = index.tz_localize("UTC").tz_convert("Europe/Warsaw")
    doy = index.dayofyear.to_numpy()
    years = (index.year - 2016).to_numpy() + doy / 365.25
    hour_local = local.hour.to_numpy()

    temp = (8.8 - 11.0 * np.cos(2 * np.pi * (doy - 17) / 365.25) + 0.045 * years
            + 3.2 * np.sin(2 * np.pi * (hour_local - 9) / 24) + _ar1(rng, n, 0.992, 4.0))
    wind = np.clip(np.exp(np.log(2.4) + 0.12 * np.cos(2 * np.pi * (doy - 30) / 365.25)
                          + _ar1(rng, n, 0.97, 0.55)), 0.1, 18)
    wet_driver = _ar1(rng, n, 0.9, 1.0)
    precip = np.where(wet_driver > 1.45, rng.exponential(0.9, n), 0.0)
    rh = np.clip(78 - 1.4 * (temp - 9) - 6 * np.sin(2 * np.pi * (hour_local - 9) / 24)
                 + 25 * (precip > 0) + rng.normal(0, 5, n), 18, 100)
    pressure = 991 + _ar1(rng, n, 0.995, 8) - 3 * (precip > 0)
    cloud = np.clip(55 + 40 * np.tanh(wet_driver) + rng.normal(0, 10, n), 0, 100)
    wdir = np.mod(250 + _ar1(rng, n, 0.98, 70), 360)
    return pd.DataFrame({
        "time": index,
        "temperature_2m": temp.round(1),
        "relative_humidity_2m": rh.round(0),
        "precipitation": precip.round(1),
        "wind_speed_10m": wind.round(2),
        "wind_direction_10m": wdir.round(0),
        "surface_pressure": pressure.round(1),
        "cloud_cover": cloud.round(0),
    })


def _policy(index: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """Relative heating emissions inside and outside Kraków over time."""
    t = ((index - pd.Timestamp("2015-01-01")) / pd.Timedelta(days=365.25)).to_numpy()
    pre_ban_years = (BAN_DATE - pd.Timestamp("2015-01-01")) / pd.Timedelta(days=365.25)
    inside = np.where(index < BAN_DATE,
                      1.0 - 0.25 * np.clip(t / pre_ban_years, 0, 1),
                      0.40 - 0.01 * np.clip(t - pre_ban_years, 0, None))
    outside = 1.0 - 0.018 * t
    return inside, outside


def simulate_pm(weather: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    index = pd.DatetimeIndex(weather["time"])
    n = len(index)
    local = index.tz_localize("UTC").tz_convert("Europe/Warsaw")
    hour = local.hour.to_numpy()
    dow = local.dayofweek.to_numpy()

    temp_smooth = weather["temperature_2m"].ewm(halflife=10).mean().to_numpy()
    demand = np.clip(16.0 - temp_smooth, 0, None)
    heat_profile = 1 + 0.55 * np.exp(-(((hour - 20) % 24) / 2.6) ** 2) \
        + 0.25 * np.exp(-((hour - 7) / 1.6) ** 2) - 0.25 * np.exp(-((hour - 14) / 3) ** 2)
    rush = 0.35 + 0.9 * np.exp(-((hour - 8) / 1.8) ** 2) + 1.0 * np.exp(-((hour - 17) / 2.2) ** 2)
    week = np.select([dow == 5, dow == 6], [0.72, 0.55], 1.0)
    wind = weather["wind_speed_10m"].to_numpy()
    dispersion = np.clip((np.maximum(wind, 0.3) / 2.4) ** -0.75, 0.35, 2.8)
    washout = np.where(weather["precipitation"].to_numpy() > 0.2, 0.62, 1.0)
    regional = np.exp(_ar1(rng, n, 0.985, 0.35))
    inside, outside = _policy(index)

    frames = []
    for st in STATIONS:
        heat_policy = (1 - st.outside_share) * inside + st.outside_share * outside
        heating = 3.3 * st.heating * demand * heat_profile * heat_policy
        traffic = 9.5 * st.traffic * rush * week
        noise = np.exp(_ar1(rng, n, 0.85, 0.2))
        pm10 = (11.0 * regional + heating + traffic + st.industrial) * dispersion * washout * noise
        frames.append(pd.DataFrame({"time": index, "station": st.code, "pollutant": "PM10",
                                    "value": pm10, "start": pd.Timestamp(st.pm10_start)}))
        if st.pm25:
            ratio = 0.56 + 0.24 * np.clip(demand / 15, 0, 1)
            pm25 = pm10 * ratio * np.exp(rng.normal(0, 0.07, n))
            frames.append(pd.DataFrame({"time": index, "station": st.code, "pollutant": "PM2.5",
                                        "value": pm25, "start": pd.Timestamp(st.pm25_start)}))
    out = pd.concat(frames, ignore_index=True)
    out = out[out["time"] >= out["start"]].drop(columns="start")
    return out.reset_index(drop=True)


def inject_quality_issues(pm: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    pm = pm.copy()
    pm["value"] = pm["value"].round(1)
    n = len(pm)
    # outages: blocks of missing hours per sensor
    pm["missing"] = False
    for (_, _), idx in pm.groupby(["station", "pollutant"]).groups.items():
        idx = np.asarray(idx)
        n_out = max(1, int(len(idx) / 24 * 0.006))
        starts = rng.choice(len(idx), n_out, replace=False)
        for s in starts:
            length = int(rng.choice([2, 5, 12, 30, 72, 160], p=[0.3, 0.25, 0.2, 0.12, 0.09, 0.04]))
            pm.loc[idx[s:s + length], "missing"] = True
    neg = rng.random(n) < 0.0003
    pm.loc[neg, "value"] = -rng.integers(1, 6, neg.sum()).astype(float)
    spike = rng.random(n) < 0.0002
    pm.loc[spike, "value"] = (pm.loc[spike, "value"] * 6 + 260).round(1)
    absurd = rng.random(n) < 0.00002
    pm.loc[absurd, "value"] = 9999.0
    return pm


def _sensor_code(station: str, pollutant: str) -> str:
    return f"{station}-{pollutant}-1g"


def _measurement_json(sensor: pd.Series, ts_text: pd.Series, value: pd.Series,
                      extra: str = "") -> pd.Series:
    val = value.map(lambda v: "null" if pd.isna(v) else repr(float(v)))
    return ('{"Kod stanowiska": "' + sensor + '", "Data": "' + ts_text + '", "Wartość": ' + val
            + extra + "}")


def _write_measurements(frame: pd.DataFrame, raw_dir: Path, source_system: str, endpoint: str,
                        params: dict, ingested_at: datetime, batch: str) -> None:
    out = pd.DataFrame({"record_json": frame["record_json"].to_numpy()})
    out["source_system"] = source_system
    out["endpoint"] = endpoint
    out["request_params"] = json.dumps(params, ensure_ascii=False, sort_keys=True)
    out["ingested_at"] = pd.Timestamp(ingested_at.replace(tzinfo=None))
    out["batch_id"] = batch
    raw_store.write_frame(out, "gios_measurements", raw_dir)


def generate(raw_dir: Path, start: date = date(2015, 1, 1), end: date | None = None,
             seed: int = 42) -> dict[str, int]:
    """Write a complete synthetic raw layer to ``raw_dir``. Returns record counts."""
    rng = np.random.default_rng(seed)
    end = end or datetime.now(UTC).date()
    run_time = datetime.combine(end, datetime.min.time()).replace(hour=5, minute=10, tzinfo=UTC)
    counts: dict[str, int] = {}

    # --- metadata -------------------------------------------------------------------
    meta_time = run_time - timedelta(days=2)
    stations = [{"Identyfikator stacji": s.station_id, "Kod stacji": s.code, "Nazwa stacji": s.name,
                 "WGS84 φ N": f"{s.lat:.6f}", "WGS84 λ E": f"{s.lon:.6f}", "Identyfikator miasta": 415,
                 "Nazwa miasta": "Kraków", "Gmina": "Kraków", "Powiat": "Kraków",
                 "Województwo": "MAŁOPOLSKIE", "Ulica": s.street} for s in STATIONS]
    station_meta = [{"Kod stacji": s.code, "Kod międzynarodowy": f"PL{s.station_id % 1000:04d}A",
                     "Nazwa stacji": s.name, "Typ stacji": s.station_type, "Typ obszaru": "miejski",
                     "Rodzaj stacji": "stacja kontenerowa stała", "Województwo": "MAŁOPOLSKIE",
                     "Miejscowość": "Kraków", "Adres": s.street, "WGS84 φ N": f"{s.lat:.6f}",
                     "WGS84 λ E": f"{s.lon:.6f}"} for s in STATIONS]
    sensors, sensor_meta = [], []
    sensor_id = 2700
    sensor_ids: dict[str, int] = {}
    for s in STATIONS:
        for pol, start_text in [("PM10", s.pm10_start), ("PM2.5", s.pm25_start if s.pm25 else None)]:
            if start_text is None:
                continue
            sensor_id += 1
            sensor_ids[_sensor_code(s.code, pol)] = sensor_id
            sensors.append({"Identyfikator stanowiska": sensor_id, "Identyfikator stacji": s.station_id,
                            "Wskaźnik": f"pył zawieszony {pol}", "Wskaźnik - wzór": pol,
                            "Wskaźnik - kod": pol, "Id wskaźnika": 3 if pol == "PM10" else 69})
            sensor_meta.append({"Kod stanowiska": _sensor_code(s.code, pol), "Kod stacji": s.code,
                                "Wskaźnik - kod": pol, "Czas uśredniania": "1g",
                                "Typ pomiaru": "automatyczny", "Data uruchomienia": start_text,
                                "Data zamknięcia": None, "Województwo": "MAŁOPOLSKIE",
                                "Nazwa strefy": "Aglomeracja Krakowska"})
    batch = raw_store.new_batch_id("synthetic-metadata")
    for table, records, endpoint in [
        ("gios_stations", stations, "station/findAll"),
        ("gios_station_metadata", station_meta, "metadata/stations"),
        ("gios_sensors", sensors, "station/sensors/{stationId}"),
        ("gios_sensor_metadata", sensor_meta, "metadata/sensors"),
    ]:
        raw_store.write_records(records, table, raw_dir, source_system="gios_api", endpoint=endpoint,
                                request_params={"synthetic": True}, ingested_at=meta_time, batch_id=batch)
        counts[table] = len(records)

    # --- weather --------------------------------------------------------------------
    index = _hours(start, run_time.replace(tzinfo=None) + timedelta(hours=24))
    weather = simulate_weather(index, rng)
    archive_end = pd.Timestamp(end - timedelta(days=6))
    w = weather.copy()
    w["time_text"] = w["time"].dt.strftime("%Y-%m-%dT%H:%M")
    variables = [c for c in w.columns if c not in {"time", "time_text"}]

    def weather_frame(rows: pd.DataFrame, source: str, endpoint: str, ingested: datetime) -> None:
        records = [{"time": t, **{v: (None if pd.isna(x) else float(x)) for v, x in zip(variables, vals,
                                                                                         strict=True)}}
                   for t, *vals in rows[["time_text", *variables]].itertuples(index=False)]
        raw_store.write_records(records, "openmeteo_weather_hourly", raw_dir, source_system=source,
                                endpoint=endpoint,
                                request_params={"location_id": "krakow_center", "synthetic": True},
                                ingested_at=ingested,
                                batch_id=raw_store.new_batch_id(f"synthetic-{source}"))

    hist = w[w["time"] < archive_end]
    weather_frame(hist, "openmeteo_archive", "v1/archive", run_time - timedelta(days=20))
    counts["openmeteo_weather_hourly"] = len(hist)
    for days_back in range(10, -1, -1):  # daily forecast-model snapshots of the recent past
        run = run_time - timedelta(days=days_back)
        lo = pd.Timestamp(run.replace(tzinfo=None)) - pd.Timedelta(days=7)
        hi = pd.Timestamp(run.replace(tzinfo=None)) + pd.Timedelta(hours=24)
        snap = w[(w["time"] >= lo) & (w["time"] < hi)].copy()
        snap["temperature_2m"] = (snap["temperature_2m"] + rng.normal(0, 0.6, len(snap))).round(1)
        weather_frame(snap, "openmeteo_forecast", "v1/forecast", run)
        counts["openmeteo_weather_hourly"] += len(snap)

    # --- measurements ---------------------------------------------------------------
    past = weather[weather["time"] <= pd.Timestamp(run_time.replace(tzinfo=None)) - pd.Timedelta(hours=1)]
    pm = inject_quality_issues(simulate_pm(past.reset_index(drop=True), rng), rng)
    pm["sensor_code"] = pm["station"] + "-" + pm["pollutant"] + "-1g"
    pm["cet_text"] = (pm["time"] + pd.Timedelta(hours=1)).dt.strftime("%Y-%m-%d %H:%M:%S")
    current_year_start = pd.Timestamp(date(end.year, 1, 1))
    counts["gios_measurements"] = 0

    # 1) yearly archive files: complete past years, CET, missing hours simply absent
    files = pm[(pm["time"] < current_year_start) & ~pm["missing"]]
    for (year, pol), grp in files.groupby([files["time"].dt.year, "pollutant"]):
        name = f"{year}_{pol.replace('.', '')}_1g.xlsx"
        rec = _measurement_json(grp["sensor_code"], grp["cet_text"], grp["value"],
                                ', "Kod stacji": "' + grp["station"] + '", "Plik": "' + name + '"')
        _write_measurements(pd.DataFrame({"record_json": rec}), raw_dir, "gios_archive_file",
                            "bank-danych-pomiarowych", {"file": name, "synthetic": True},
                            run_time - timedelta(days=30), raw_store.new_batch_id(f"synthetic-file-{year}"))
        counts["gios_measurements"] += len(grp)

    # 2) API archival backfill for the current year (nulls for missing hours)
    api_arch = pm[(pm["time"] >= current_year_start)
                  & (pm["time"] < pd.Timestamp(end - timedelta(days=21)))].copy()
    api_arch.loc[api_arch["missing"], "value"] = np.nan
    rec = _measurement_json(api_arch["sensor_code"], api_arch["cet_text"], api_arch["value"])
    _write_measurements(pd.DataFrame({"record_json": rec}), raw_dir, "gios_api_archive",
                        "archivalData/getDataBySensor/{idSensor}", {"synthetic": True},
                        run_time - timedelta(days=21), raw_store.new_batch_id("synthetic-api-archive"))
    counts["gios_measurements"] += len(api_arch)

    # 3) daily current-API snapshots over the last 30 days (local time, unverified)
    pm["local_text"] = (pm["time"].dt.tz_localize("UTC").dt.tz_convert("Europe/Warsaw")
                        .dt.strftime("%Y-%m-%d %H:%M:%S"))
    for days_back in range(30, -1, -1):
        run = run_time - timedelta(days=days_back)
        run_naive = pd.Timestamp(run.replace(tzinfo=None))
        snap = pm[(pm["time"] > run_naive - pd.Timedelta(hours=72))
                  & (pm["time"] <= run_naive - pd.Timedelta(hours=1))].copy()
        snap["value"] = (snap["value"] * np.exp(rng.normal(0, 0.03, len(snap)))).round(1)
        snap.loc[snap["missing"], "value"] = np.nan
        newest = snap["time"] >= run_naive - pd.Timedelta(hours=2)
        snap.loc[newest & (rng.random(len(snap)) < 0.3), "value"] = np.nan  # not yet reported
        rec = _measurement_json(snap["sensor_code"], snap["local_text"], snap["value"])
        _write_measurements(pd.DataFrame({"record_json": rec}), raw_dir, "gios_api_current",
                            "data/getData/{sensorId}", {"synthetic": True},
                            run, raw_store.new_batch_id("synthetic-current"))
        counts["gios_measurements"] += len(snap)

    marker = Path(raw_dir) / "_SYNTHETIC"
    marker.write_text(f"Synthetic sample generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC, seed={seed}\n")
    return counts
