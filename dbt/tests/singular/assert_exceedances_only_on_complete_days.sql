-- Norm exceedances may only be evaluated for days with enough valid hours.
select *
from {{ ref('fct_air_quality_daily') }}
where not is_complete_day
  and (exceeds_who_24h is not null or exceeds_eu_24h is not null)
