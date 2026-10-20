{#- Domain logic shared by models and tests (one definition, used in several places). -#}

{#
  An isolated spike: a single hour far above BOTH neighbouring hours. Real smog episodes
  build up and decay over several hours; one-hour peaks of hundreds of µg/m³ that vanish
  in the next hour are typical device/transmission errors. Neighbours must be exactly one
  hour apart; at gaps the reading cannot be judged and is kept.
#}
{% macro is_isolated_spike(value, prev_value, next_value, prev_gap_hours, next_gap_hours) -%}
(
      {{ prev_gap_hours }} = 1 and {{ next_gap_hours }} = 1
  and {{ prev_value }} is not null and {{ next_value }} is not null
  and {{ value }} - {{ prev_value }} > {{ var('isolated_spike_min_jump') }}
  and {{ value }} - {{ next_value }} > {{ var('isolated_spike_min_jump') }}
  and {{ value }} > {{ var('isolated_spike_min_ratio') }}
                    * (({{ prev_value }} + {{ next_value }}) / 2.0 + 1)
)
{%- endmacro %}


{# Meteorological season of a month number. #}
{% macro season_of_month(month_column) -%}
case
  when {{ month_column }} in (12, 1, 2) then 'winter'
  when {{ month_column }} in (3, 4, 5) then 'spring'
  when {{ month_column }} in (6, 7, 8) then 'summer'
  else 'autumn'
end
{%- endmacro %}


{# Heating season label "2019/20" for October-March, NULL otherwise. #}
{% macro heating_season_label(date_column) -%}
case
  when extract(month from {{ date_column }}) >= 10
    then cast(extract(year from {{ date_column }}) as {{ dbt.type_string() }})
         || '/' || right(cast(extract(year from {{ date_column }}) + 1 as {{ dbt.type_string() }}), 2)
  when extract(month from {{ date_column }}) <= 3
    then cast(extract(year from {{ date_column }}) - 1 as {{ dbt.type_string() }})
         || '/' || right(cast(extract(year from {{ date_column }}) as {{ dbt.type_string() }}), 2)
end
{%- endmacro %}


{# Source preference when the same hour arrives from several sources (lower = better). #}
{% macro gios_source_priority(source_column) -%}
case {{ source_column }}
  when 'gios_archive_file' then 1   -- verified yearly packages
  when 'gios_api_archive' then 2    -- archival service
  when 'gios_api_current' then 3    -- real-time, unverified
  else 9
end
{%- endmacro %}


{# Pollutant code normalisation: PM25 / pm2.5 / PM2,5 -> PM2.5 #}
{% macro normalize_pollutant(column) -%}
case
  when upper(replace(replace({{ column }}, ',', '.'), '.', '')) = 'PM25' then 'PM2.5'
  else upper({{ column }})
end
{%- endmacro %}
