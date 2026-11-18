# Coal ban effect – weather-normalised regression

Data exported: 2026-11-18T14:07:15+00:00. Heating-season days (Oct–Mar), city mean of stations with a complete day, HAC standard errors (7 lags).

| Pollutant | Specification | Days | Naive change | Weather-adjusted change | 95 % CI | p | R² |
|---|---|---:|---:|---:|---:|---:|---:|
| PM10 | no trend | 1961 | -37.3 % | **-37.6 %** | -41.3 … -33.5 % | 0.000 | 0.57 |
| PM10 | with trend | 1961 | -37.3 % | **-5.8 %** | -14.2 … +3.4 % | 0.208 | 0.62 |
| PM2.5 | no trend | 2113 | -40.5 % | **-40.9 %** | -44.8 … -36.7 % | 0.000 | 0.56 |
| PM2.5 | with trend | 2113 | -40.5 % | **+2.6 %** | -7.6 … +14.0 % | 0.625 | 0.62 |

How to read it:

* *Naive change* compares all heating-season days after 2019-09-01 with those before.
* *No trend*: relative difference after vs before the ban on days with the same weather, month and weekday.
* *With trend*: the step at the ban beyond a linear trend. A much smaller step than the no-trend effect means the improvement was gradual (stove replacement before the ban) rather than abrupt.
* This is an observational before/after design. Other changes in the same period (traffic, regional emissions, COVID-19 in 2020) are not separated. A control area without the ban (difference-in-differences) would strengthen the conclusion; see README.
