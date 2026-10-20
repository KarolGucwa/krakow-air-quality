-- Mean concentration by day of week and local hour, split by heating / non-heating season.
with hourly as (

    select
        h.station_code,
        h.pollutant_code,
        h.hour_local,
        h.value_ugm3,
        d.iso_day_of_week,
        d.day_name,
        case when d.is_heating_season then 'heating season' else 'non-heating season' end as season_group
    from {{ ref('fct_air_quality_hourly') }} as h
    inner join {{ ref('dim_date') }} as d
        on h.date_day = d.date_day

)

select
    station_code,
    pollutant_code,
    season_group,
    iso_day_of_week,
    day_name,
    hour_local,
    count(*)            as hours,
    avg(value_ugm3)     as mean_ugm3
from hourly
group by 1, 2, 3, 4, 5, 6
