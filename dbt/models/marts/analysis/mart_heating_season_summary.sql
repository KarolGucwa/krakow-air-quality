{#-
  One row per station, pollutant and heating season (October-March), e.g. "2019/20".
  Only complete days are used. Weather columns make it visible how cold (or mild) the
  season was, which matters when comparing seasons before and after the coal ban.
-#}
with daily as (

    select
        f.*,
        d.heating_season,
        d.ban_period
    from {{ ref('fct_air_quality_daily') }} as f
    inner join {{ ref('dim_date') }} as d
        on f.date_day = d.date_day
    where f.is_complete_day
      and d.is_heating_season

)

select
    station_code,
    pollutant_code,
    heating_season,
    min(ban_period)                                                     as ban_period,
    count(*)                                                            as complete_days,
    avg(mean_ugm3)                                                      as mean_ugm3,
    max(mean_ugm3)                                                      as max_daily_mean_ugm3,
    sum(case when exceeds_who_24h then 1 else 0 end)                    as days_above_who_24h,
    sum(case when exceeds_eu_24h then 1 else 0 end)                     as days_above_eu_24h,
    avg(temp_mean_c)                                                    as temp_mean_c,
    sum(heating_degree_days)                                            as heating_degree_days,
    avg(wind_mean_ms)                                                   as wind_mean_ms
from daily
where cast(substr(heating_season, 1, 4) as integer) >= {{ var('analysis_first_season_start_year') }}
group by station_code, pollutant_code, heating_season
