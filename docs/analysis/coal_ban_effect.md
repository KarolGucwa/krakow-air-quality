# Coal ban effect – weather-normalised regression

Data exported: 2026-11-27T15:11:08+00:00. Heating-season days (Oct–Mar), city mean of stations with a complete day, HAC standard errors (7 lags).

| Pollutant | Specification | Days | Naive change | Weather-adjusted change | 95 % CI | p | R² |
|---|---|---:|---:|---:|---:|---:|---:|
| PM10 | no trend | 1970 | -37.6 % | **-37.7 %** | -41.5 … -33.7 % | 0.000 | 0.57 |
| PM10 | with trend | 1970 | -37.6 % | **-5.6 %** | -14.0 … +3.7 % | 0.229 | 0.62 |
| PM2.5 | no trend | 2122 | -40.7 % | **-41.1 %** | -45.0 … -36.9 % | 0.000 | 0.56 |
| PM2.5 | with trend | 2122 | -40.7 % | **+3.1 %** | -7.1 … +14.5 % | 0.564 | 0.62 |

How to read it:

* *Naive change* compares all heating-season days after 2019-09-01 with those before.
* *No trend*: relative difference after vs before the ban on days with the same weather, month and weekday.
* *With trend*: the step at the ban beyond a linear trend. A much smaller step than the no-trend effect means the improvement was gradual (stove replacement before the ban) rather than abrupt.
* This is an observational before/after design. Other changes in the same period (traffic, regional emissions, COVID-19 in 2020) are not separated. A control area without the ban (difference-in-differences) would strengthen the conclusion; see README.
