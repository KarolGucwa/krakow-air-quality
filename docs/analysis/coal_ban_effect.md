# Coal ban effect – weather-normalised regression

Data exported: 2026-11-19T14:45:17+00:00. Heating-season days (Oct–Mar), city mean of stations with a complete day, HAC standard errors (7 lags).

| Pollutant | Specification | Days | Naive change | Weather-adjusted change | 95 % CI | p | R² |
|---|---|---:|---:|---:|---:|---:|---:|
| PM10 | no trend | 1962 | -37.4 % | **-37.6 %** | -41.4 … -33.6 % | 0.000 | 0.57 |
| PM10 | with trend | 1962 | -37.4 % | **-5.7 %** | -14.2 … +3.6 % | 0.221 | 0.62 |
| PM2.5 | no trend | 2114 | -40.5 % | **-41.0 %** | -44.9 … -36.8 % | 0.000 | 0.56 |
| PM2.5 | with trend | 2114 | -40.5 % | **+2.8 %** | -7.4 … +14.2 % | 0.601 | 0.62 |

How to read it:

* *Naive change* compares all heating-season days after 2019-09-01 with those before.
* *No trend*: relative difference after vs before the ban on days with the same weather, month and weekday.
* *With trend*: the step at the ban beyond a linear trend. A much smaller step than the no-trend effect means the improvement was gradual (stove replacement before the ban) rather than abrupt.
* This is an observational before/after design. Other changes in the same period (traffic, regional emissions, COVID-19 in 2020) are not separated. A control area without the ban (difference-in-differences) would strengthen the conclusion; see README.
