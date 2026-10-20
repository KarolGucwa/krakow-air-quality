-- A measurement timestamp later than "now" means a time-zone conversion bug.
select *
from {{ ref('fct_air_quality_hourly') }}
where measured_at_utc > {{ dbt.dateadd('hour', 1, dbt.current_timestamp()) }}
