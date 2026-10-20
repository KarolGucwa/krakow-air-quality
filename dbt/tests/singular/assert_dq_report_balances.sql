-- The monthly DQ report must account for every expected hour exactly once.
select *
from {{ ref('dq_station_monthly_report') }}
where missing_hours < 0
   or valid_hours + rejected_hours + missing_hours <> expected_hours
