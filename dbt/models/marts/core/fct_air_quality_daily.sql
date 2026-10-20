{#-
  Fact: daily mean concentration per station and pollutant with weather of the day.
  A day counts as complete with >= daily_min_valid_hours (18 of 24, i.e. 75 %) valid
  hours; norm exceedances are evaluated only for complete days, otherwise NULL, so that
  data gaps neither create nor hide exceedances.
-#}
with hourly as (

    select * from {{ ref('fct_air_quality_hourly') }}

),

daily as (

    select
        station_code,
        pollutant_code,
        date_day,
        count(*)            as valid_hours,
        avg(value_ugm3)     as mean_ugm3,
        min(value_ugm3)     as min_ugm3,
        max(value_ugm3)     as max_ugm3
    from hourly
    group by station_code, pollutant_code, date_day

),

pollutants as (

    select * from {{ ref('dim_pollutant') }}

),

weather as (

    select * from {{ ref('int_weather__daily') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['d.station_code', 'd.pollutant_code', 'd.date_day']) }} as daily_key,
    d.station_code,
    d.pollutant_code,
    d.date_day,
    d.valid_hours,
    d.valid_hours >= {{ var('daily_min_valid_hours') }}                    as is_complete_day,
    d.mean_ugm3,
    d.min_ugm3,
    d.max_ugm3,
    p.who_24h_ugm3,
    case when d.valid_hours >= {{ var('daily_min_valid_hours') }}
         then d.mean_ugm3 > p.who_24h_ugm3 end                            as exceeds_who_24h,
    case when d.valid_hours >= {{ var('daily_min_valid_hours') }} and p.eu_24h_limit_ugm3 is not null
         then d.mean_ugm3 > p.eu_24h_limit_ugm3 end                       as exceeds_eu_24h,
    w.temp_mean_c,
    w.temp_min_c,
    w.temp_max_c,
    w.wind_mean_ms,
    w.precipitation_sum_mm,
    w.humidity_mean_pct,
    w.pressure_mean_hpa,
    w.heating_degree_days
from daily as d
inner join pollutants as p
    on d.pollutant_code = p.pollutant_code
left join weather as w
    on d.date_day = w.measurement_date
