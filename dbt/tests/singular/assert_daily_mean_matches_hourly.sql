-- Reconciliation: the daily fact must equal a fresh aggregation of the hourly fact.
with recomputed as (

    select station_code, pollutant_code, date_day, avg(value_ugm3) as mean_ugm3, count(*) as valid_hours
    from {{ ref('fct_air_quality_hourly') }}
    group by 1, 2, 3

)

select d.*
from {{ ref('fct_air_quality_daily') }} as d
left join recomputed as r
    on d.station_code = r.station_code
   and d.pollutant_code = r.pollutant_code
   and d.date_day = r.date_day
where r.station_code is null
   or d.valid_hours <> r.valid_hours
   or abs(d.mean_ugm3 - r.mean_ugm3) > 0.001
