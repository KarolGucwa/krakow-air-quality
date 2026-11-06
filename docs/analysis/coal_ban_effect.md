# Coal ban effect – weather-normalised regression

Data exported: 2026-11-06T13:00:05+00:00. Heating-season days (Oct–Mar), city mean of stations with a complete day, HAC standard errors (7 lags).

| Pollutant | Specification | Days | Naive change | Weather-adjusted change | 95 % CI | p | R² |
|---|---|---:|---:|---:|---:|---:|---:|
| PM10 | no trend | 1949 | -37.3 % | **-37.4 %** | -41.2 … -33.4 % | 0.000 | 0.57 |
| PM10 | with trend | 1949 | -37.3 % | **-5.8 %** | -14.3 … +3.5 % | 0.212 | 0.62 |
| PM2.5 | no trend | 2101 | -40.4 % | **-40.7 %** | -44.6 … -36.5 % | 0.000 | 0.56 |
| PM2.5 | with trend | 2101 | -40.4 % | **+2.5 %** | -7.8 … +13.9 % | 0.650 | 0.62 |

How to read it:

* *Naive change* compares all heating-season days after 2019-09-01 with those before.
* *No trend*: relative difference after vs before the ban on days with the same weather, month and weekday.
* *With trend*: the step at the ban beyond a linear trend. A much smaller step than the no-trend effect means the improvement was gradual (stove replacement before the ban) rather than abrupt.
* This is an observational before/after design. Other changes in the same period (traffic, regional emissions, COVID-19 in 2020) are not separated. A control area without the ban (difference-in-differences) would strengthen the conclusion; see README.
