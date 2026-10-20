-- How daily PM responds to temperature and wind: mean concentration per weather band.
with daily as (

    select
        f.station_code,
        f.pollutant_code,
        f.mean_ugm3,
        d.ban_period,
        cast(floor(f.temp_mean_c / 2.5) * 2.5 as double)                as temp_band_c,
        cast(floor(f.wind_mean_ms * 2) / 2 as double)                   as wind_band_ms
    from {{ ref('fct_air_quality_daily') }} as f
    inner join {{ ref('dim_date') }} as d
        on f.date_day = d.date_day
    where f.is_complete_day
      and f.temp_mean_c is not null

)

select
    station_code,
    pollutant_code,
    ban_period,
    'temperature' as driver,
    temp_band_c   as band_value,
    count(*)      as days,
    avg(mean_ugm3) as mean_ugm3
from daily
group by 1, 2, 3, 4, 5

union all

select
    station_code,
    pollutant_code,
    ban_period,
    'wind'         as driver,
    least(wind_band_ms, 8.0) as band_value,
    count(*)       as days,
    avg(mean_ugm3) as mean_ugm3
from daily
group by 1, 2, 3, 4, 5
