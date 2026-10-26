# Coal ban effect – weather-normalised regression

Data exported: 2026-10-26T11:12:05+00:00. Heating-season days (Oct–Mar), city mean of stations with a complete day, HAC standard errors (7 lags).

| Pollutant | Specification | Days | Naive change | Weather-adjusted change | 95 % CI | p | R² |
|---|---|---:|---:|---:|---:|---:|---:|
| PM10 | no trend | 1938 | -37.1 % | **-37.3 %** | -41.1 … -33.3 % | 0.000 | 0.57 |
| PM10 | with trend | 1938 | -37.1 % | **-6.2 %** | -14.7 … +3.1 % | 0.187 | 0.62 |
| PM2.5 | no trend | 2091 | -40.2 % | **-40.5 %** | -44.4 … -36.3 % | 0.000 | 0.56 |
| PM2.5 | with trend | 2091 | -40.2 % | **+2.1 %** | -8.2 … +13.5 % | 0.706 | 0.62 |

How to read it:

* *Naive change* compares all heating-season days after 2019-09-01 with those before.
* *No trend*: relative difference after vs before the ban on days with the same weather, month and weekday.
* *With trend*: the step at the ban beyond a linear trend. A much smaller step than the no-trend effect means the improvement was gradual (stove replacement before the ban) rather than abrupt.
* This is an observational before/after design. Other changes in the same period (traffic, regional emissions, COVID-19 in 2020) are not separated. A control area without the ban (difference-in-differences) would strengthen the conclusion; see README.
