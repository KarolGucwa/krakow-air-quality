# Coal ban effect – weather-normalised regression

Data exported: 2026-11-16T13:57:20+00:00. Heating-season days (Oct–Mar), city mean of stations with a complete day, HAC standard errors (7 lags).

| Pollutant | Specification | Days | Naive change | Weather-adjusted change | 95 % CI | p | R² |
|---|---|---:|---:|---:|---:|---:|---:|
| PM10 | no trend | 1959 | -37.3 % | **-37.6 %** | -41.3 … -33.6 % | 0.000 | 0.57 |
| PM10 | with trend | 1959 | -37.3 % | **-6.1 %** | -14.5 … +3.1 % | 0.186 | 0.62 |
| PM2.5 | no trend | 2111 | -40.4 % | **-40.9 %** | -44.7 … -36.7 % | 0.000 | 0.56 |
| PM2.5 | with trend | 2111 | -40.4 % | **+2.3 %** | -7.8 … +13.6 % | 0.664 | 0.62 |

How to read it:

* *Naive change* compares all heating-season days after 2019-09-01 with those before.
* *No trend*: relative difference after vs before the ban on days with the same weather, month and weekday.
* *With trend*: the step at the ban beyond a linear trend. A much smaller step than the no-trend effect means the improvement was gradual (stove replacement before the ban) rather than abrupt.
* This is an observational before/after design. Other changes in the same period (traffic, regional emissions, COVID-19 in 2020) are not separated. A control area without the ban (difference-in-differences) would strengthen the conclusion; see README.
