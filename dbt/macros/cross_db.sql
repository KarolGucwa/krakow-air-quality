{#-
  Cross-database helpers. Models call these instead of engine-specific functions so the
  same project runs on DuckDB (default) and Databricks (`--target databricks`).
  adapter.dispatch picks `duckdb__*` or `databricks__*` / `spark__*` implementations.
-#}

{# Extract a top-level JSON field as text. Keys may contain spaces and Polish letters. #}
{% macro json_get(column, key) -%}
  {{ return(adapter.dispatch('json_get', 'krakow_air')(column, key)) }}
{%- endmacro %}

{% macro default__json_get(column, key) -%}
  json_extract_string({{ column }}, '$."{{ key }}"')
{%- endmacro %}

{% macro spark__json_get(column, key) -%}
  get_json_object({{ column }}, "$['{{ key }}']")
{%- endmacro %}

{% macro databricks__json_get(column, key) -%}
  {{ spark__json_get(column, key) }}
{%- endmacro %}


{# Interpret a naive local timestamp in `tz` and return the naive UTC timestamp. #}
{% macro local_to_utc(column, tz) -%}
  {{ return(adapter.dispatch('local_to_utc', 'krakow_air')(column, tz)) }}
{%- endmacro %}

{% macro default__local_to_utc(column, tz) -%}
  timezone('UTC', timezone('{{ tz }}', {{ column }}))
{%- endmacro %}

{% macro spark__local_to_utc(column, tz) -%}
  to_utc_timestamp({{ column }}, '{{ tz }}')
{%- endmacro %}

{% macro databricks__local_to_utc(column, tz) -%}
  {{ spark__local_to_utc(column, tz) }}
{%- endmacro %}


{# Convert a naive UTC timestamp to naive local time in `tz`. #}
{% macro utc_to_local(column, tz) -%}
  {{ return(adapter.dispatch('utc_to_local', 'krakow_air')(column, tz)) }}
{%- endmacro %}

{% macro default__utc_to_local(column, tz) -%}
  timezone('{{ tz }}', timezone('UTC', {{ column }}))
{%- endmacro %}

{% macro spark__utc_to_local(column, tz) -%}
  from_utc_timestamp({{ column }}, '{{ tz }}')
{%- endmacro %}

{% macro databricks__utc_to_local(column, tz) -%}
  {{ spark__utc_to_local(column, tz) }}
{%- endmacro %}


{# ISO day of week: Monday = 1 ... Sunday = 7. #}
{% macro iso_day_of_week(column) -%}
  {{ return(adapter.dispatch('iso_day_of_week', 'krakow_air')(column)) }}
{%- endmacro %}

{% macro default__iso_day_of_week(column) -%}
  isodow({{ column }})
{%- endmacro %}

{% macro spark__iso_day_of_week(column) -%}
  ((dayofweek({{ column }}) + 5) % 7 + 1)
{%- endmacro %}

{% macro databricks__iso_day_of_week(column) -%}
  {{ spark__iso_day_of_week(column) }}
{%- endmacro %}


{# Text to timestamp, NULL when unparseable. #}
{% macro try_to_timestamp(column) -%}
  {{ return(adapter.dispatch('try_to_timestamp', 'krakow_air')(column)) }}
{%- endmacro %}

{% macro default__try_to_timestamp(column) -%}
  try_cast(replace({{ column }}, 'T', ' ') as timestamp)
{%- endmacro %}

{% macro spark__try_to_timestamp(column) -%}
  try_to_timestamp(replace({{ column }}, 'T', ' '))
{%- endmacro %}

{% macro databricks__try_to_timestamp(column) -%}
  {{ spark__try_to_timestamp(column) }}
{%- endmacro %}


{# Text to double, NULL when unparseable (also accepts a decimal comma). #}
{% macro try_to_double(column) -%}
  {{ return(adapter.dispatch('try_to_double', 'krakow_air')(column)) }}
{%- endmacro %}

{% macro default__try_to_double(column) -%}
  try_cast(replace({{ column }}, ',', '.') as double)
{%- endmacro %}

{% macro spark__try_to_double(column) -%}
  try_cast(replace({{ column }}, ',', '.') as double)
{%- endmacro %}

{% macro databricks__try_to_double(column) -%}
  {{ spark__try_to_double(column) }}
{%- endmacro %}
