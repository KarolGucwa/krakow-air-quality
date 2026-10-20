{#-
  One row per (sensor, hour) — the preferred version — with a validation verdict.
  Rules are applied in order; the first matching rule gives the rejection reason:
    missing_value   API returned the hour without a value (null)
    negative_value  physically impossible concentration
    out_of_range    above the plausibility ceiling from seeds/pollutants.csv
    isolated_spike  one-hour peak far above both neighbours (macro is_isolated_spike)
  Rejected rows stay in this model (for the DQ report); marts use is_valid = true only.
-#}
with current_versions as (

    select * from {{ ref('int_gios__measurements_versioned') }}
    where version_rank = 1
      and measured_at_utc is not null

),

limits as (

    select pollutant_code, max_plausible_ugm3 from {{ ref('pollutants') }}

),

with_neighbours as (

    select
        v.*,
        l.max_plausible_ugm3,
        lag(v.value_ugm3) over w                                            as prev_value_ugm3,
        lead(v.value_ugm3) over w                                           as next_value_ugm3,
        {{ dbt.datediff('lag(v.measured_at_utc) over w', 'v.measured_at_utc', 'hour') }}  as prev_gap_hours,
        {{ dbt.datediff('v.measured_at_utc', 'lead(v.measured_at_utc) over w', 'hour') }} as next_gap_hours
    from current_versions as v
    left join limits as l
        on v.pollutant_code = l.pollutant_code
    window w as (partition by v.sensor_code order by v.measured_at_utc)

),

verdict as (

    select
        *,
        case
            when value_ugm3 is null then 'missing_value'
            when value_ugm3 < 0 then 'negative_value'
            when value_ugm3 > max_plausible_ugm3 then 'out_of_range'
            when {{ is_isolated_spike('value_ugm3', 'prev_value_ugm3', 'next_value_ugm3',
                                      'prev_gap_hours', 'next_gap_hours') }} then 'isolated_spike'
        end as rejection_reason
    from with_neighbours

)

select
    raw_record_id,
    sensor_code,
    station_code,
    pollutant_code,
    measured_at_utc,
    value_ugm3,
    source_system,
    ingested_at,
    version_count,
    rejection_reason,
    rejection_reason is null as is_valid
from verdict
