{#-
  Was the drop in PM after the solid-fuel ban (2019-09-01) larger than weather explains?

  Simply comparing winters before and after is biased: winters after 2019 were milder
  and windier days dilute pollution. Here heating-season days are grouped into weather
  strata (temperature × wind × rain). Within each stratum the mean before and after the
  ban is compared, then strata are averaged with weights = number of days after the ban.
  The result answers: "on days with the same weather, how much lower is PM now?"

  `naive_change_pct` (plain before/after mean) is reported next to it for contrast.
  A regression-based estimate with uncertainty is in analysis/coal_ban_effect.py.
-#}
with days as (

    select
        f.station_code,
        f.pollutant_code,
        f.mean_ugm3,
        d.is_after_coal_ban,
        case
            when f.temp_mean_c < -5 then 'a: < -5 °C'
            when f.temp_mean_c < 0 then 'b: -5..0 °C'
            when f.temp_mean_c < 5 then 'c: 0..5 °C'
            when f.temp_mean_c < 10 then 'd: 5..10 °C'
            else 'e: >= 10 °C'
        end as temp_band,
        case
            when f.wind_mean_ms < 1.5 then 'a: calm < 1.5 m/s'
            when f.wind_mean_ms < 3 then 'b: 1.5..3 m/s'
            when f.wind_mean_ms < 5 then 'c: 3..5 m/s'
            else 'd: >= 5 m/s'
        end as wind_band,
        case when f.precipitation_sum_mm >= 1 then 'wet' else 'dry' end as rain_band
    from {{ ref('fct_air_quality_daily') }} as f
    inner join {{ ref('dim_date') }} as d
        on f.date_day = d.date_day
    where f.is_complete_day
      and d.is_heating_season
      and f.temp_mean_c is not null
      and f.wind_mean_ms is not null
      and cast(substr(d.heating_season, 1, 4) as integer) >= {{ var('analysis_first_season_start_year') }}

),

strata as (

    select
        station_code,
        pollutant_code,
        temp_band,
        wind_band,
        rain_band,
        avg(case when not is_after_coal_ban then mean_ugm3 end)         as mean_before,
        avg(case when is_after_coal_ban then mean_ugm3 end)             as mean_after,
        sum(case when not is_after_coal_ban then 1 else 0 end)          as days_before,
        sum(case when is_after_coal_ban then 1 else 0 end)              as days_after
    from days
    group by 1, 2, 3, 4, 5

),

comparable as (

    select * from strata
    where days_before >= 5 and days_after >= 5

),

stratified as (

    select
        station_code,
        pollutant_code,
        sum(days_after * mean_before) / sum(days_after)                 as weather_matched_before_ugm3,
        sum(days_after * mean_after) / sum(days_after)                  as weather_matched_after_ugm3,
        count(*)                                                        as strata_used,
        sum(days_after)                                                 as matched_days_after
    from comparable
    group by 1, 2

),

naive as (

    select
        station_code,
        pollutant_code,
        avg(case when not is_after_coal_ban then mean_ugm3 end)         as naive_before_ugm3,
        avg(case when is_after_coal_ban then mean_ugm3 end)             as naive_after_ugm3,
        sum(case when not is_after_coal_ban then 1 else 0 end)          as days_before,
        sum(case when is_after_coal_ban then 1 else 0 end)              as days_after
    from days
    group by 1, 2

)

select
    n.station_code,
    n.pollutant_code,
    n.days_before,
    n.days_after,
    n.naive_before_ugm3,
    n.naive_after_ugm3,
    100.0 * (n.naive_after_ugm3 - n.naive_before_ugm3) / nullif(n.naive_before_ugm3, 0)   as naive_change_pct,
    s.weather_matched_before_ugm3,
    s.weather_matched_after_ugm3,
    100.0 * (s.weather_matched_after_ugm3 - s.weather_matched_before_ugm3)
        / nullif(s.weather_matched_before_ugm3, 0)                                       as weather_adjusted_change_pct,
    s.strata_used,
    s.matched_days_after
from naive as n
left join stratified as s
    on n.station_code = s.station_code
   and n.pollutant_code = s.pollutant_code
where n.days_before > 0 and n.days_after > 0
