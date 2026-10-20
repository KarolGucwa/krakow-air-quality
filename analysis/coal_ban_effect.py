"""Weather-normalised estimate of the 2019 solid-fuel ban effect (regression).

Complements the dbt model `mart_coal_ban_weather_stratified` with a model that controls
for several weather variables at once and gives a confidence interval.

Model (heating-season days, complete days only, city mean over stations):

    log(PM) = b0 + b_ban * after_ban
              + temperature + temperature^2 + log(wind) + rain day + humidity
              + month fixed effects + weekday fixed effects  [+ linear trend]

exp(b_ban) - 1 is the relative change after 2019-09-01 at equal weather and calendar.
Standard errors are HAC (Newey-West, 7 lags) because consecutive days are correlated.

Two specifications are reported because they answer different questions:
* without trend: "how much lower is PM after the ban, weather held equal?"
* with trend:    "how big was the step at the ban, beyond the gradual decline?"
  (Kraków replaced stoves gradually for years before 2019, so part of the improvement
  is a trend, not a step.)

Usage:
    python analysis/coal_ban_effect.py --marts data/marts --out docs/analysis/coal_ban_effect.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]


def read_parquet(path: Path) -> pd.DataFrame:
    # DuckDB instead of pyarrow: pyarrow's Parquet module is blocked on some Windows machines.
    return duckdb.sql(f"select * from read_parquet('{path.as_posix()}')").df()


def load(marts: Path) -> tuple[pd.DataFrame, dict]:
    daily = read_parquet(marts / "marts__fct_air_quality_daily.parquet")
    dates = read_parquet(marts / "marts__dim_date.parquet")
    meta_path = marts / "_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    df = daily.merge(dates, on="date_day")
    df = df[df["is_complete_day"] & df["is_heating_season"] & df["temp_mean_c"].notna()]
    return df, meta


def city_daily(df: pd.DataFrame, pollutant: str) -> pd.DataFrame:
    sub = df[df["pollutant_code"] == pollutant]
    city = (sub.groupby("date_day")
            .agg(pm=("mean_ugm3", "mean"), stations=("station_code", "nunique"),
                 temp=("temp_mean_c", "first"), wind=("wind_mean_ms", "first"),
                 rain=("precipitation_sum_mm", "first"), rh=("humidity_mean_pct", "first"),
                 month=("month", "first"), dow=("iso_day_of_week", "first"),
                 after_ban=("is_after_coal_ban", "first"))
            .reset_index())
    city = city[(city["stations"] >= max(2, city["stations"].median() // 2)) & (city["pm"] > 0)]
    city["log_pm"] = np.log(city["pm"])
    city["log_wind"] = np.log(city["wind"].clip(lower=0.3))
    city["rain_day"] = (city["rain"] >= 1).astype(int)
    city["after_ban"] = city["after_ban"].astype(int)
    city["trend_years"] = (pd.to_datetime(city["date_day"]) - pd.Timestamp("2019-09-01")).dt.days / 365.25
    return city.sort_values("date_day").reset_index(drop=True)


def fit(city: pd.DataFrame, with_trend: bool) -> dict:
    formula = ("log_pm ~ after_ban + temp + I(temp**2) + log_wind + rain_day + rh"
               " + C(month) + C(dow)" + (" + trend_years" if with_trend else ""))
    model = smf.ols(formula, data=city).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
    b, se = model.params["after_ban"], model.bse["after_ban"]
    naive = city.loc[city["after_ban"] == 1, "pm"].mean() / city.loc[city["after_ban"] == 0, "pm"].mean() - 1
    return {
        "effect_pct": 100 * (np.exp(b) - 1),
        "ci_low_pct": 100 * (np.exp(b - 1.96 * se) - 1),
        "ci_high_pct": 100 * (np.exp(b + 1.96 * se) - 1),
        "p_value": float(model.pvalues["after_ban"]),
        "naive_pct": 100 * naive,
        "r2": float(model.rsquared),
        "days": int(model.nobs),
        "temp_coef": float(model.params["temp"]),
        "wind_coef": float(model.params["log_wind"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marts", type=Path, default=ROOT / "data" / "marts")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "analysis" / "coal_ban_effect.md")
    args = parser.parse_args()

    df, meta = load(args.marts)
    rows = []
    for pollutant in sorted(df["pollutant_code"].unique()):
        city = city_daily(df, pollutant)
        if city["after_ban"].nunique() < 2:
            continue
        for with_trend in (False, True):
            rows.append({"pollutant": pollutant, "specification": "with trend" if with_trend else "no trend",
                         **fit(city, with_trend)})
    result = pd.DataFrame(rows)
    target = (args.marts / "analysis__coal_ban_regression.parquet").as_posix()
    con = duckdb.connect()
    con.register("result", result)
    con.execute(f"copy result to '{target}' (format parquet)")
    con.close()

    lines = ["# Coal ban effect – weather-normalised regression", ""]
    if meta.get("data_mode") == "synthetic":
        lines += ["> **DEMO – synthetic data.** Generated by `aq generate-sample`; numbers below only show",
                  "> what the analysis produces. Re-run on real data before drawing conclusions.", ""]
    lines += [f"Data exported: {meta.get('exported_at', 'unknown')}. Heating-season days (Oct–Mar), "
              "city mean of stations with a complete day, HAC standard errors (7 lags).", "",
              "| Pollutant | Specification | Days | Naive change | Weather-adjusted change | 95 % CI | p | R² |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in result.itertuples():
        lines.append(f"| {r.pollutant} | {r.specification} | {r.days} | {r.naive_pct:+.1f} % | "
                     f"**{r.effect_pct:+.1f} %** | {r.ci_low_pct:+.1f} … {r.ci_high_pct:+.1f} % | "
                     f"{r.p_value:.3f} | {r.r2:.2f} |")
    lines += ["", "How to read it:", "",
              "* *Naive change* compares all heating-season days after 2019-09-01 with those before.",
              "* *No trend*: relative difference after vs before the ban on days with the same weather, "
              "month and weekday.",
              "* *With trend*: the step at the ban beyond a linear trend. A much smaller step than the "
              "no-trend effect means the improvement was gradual (stove replacement before the ban) "
              "rather than abrupt.",
              "* This is an observational before/after design. Other changes in the same period "
              "(traffic, regional emissions, COVID-19 in 2020) are not separated. A control area "
              "without the ban (difference-in-differences) would strengthen the conclusion; see README.",
              ""]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
