select
    pollutant_code,
    pollutant_name,
    who_24h_ugm3,
    who_annual_ugm3,
    eu_24h_limit_ugm3,
    eu_24h_allowed_exceedances,
    eu_annual_limit_ugm3,
    max_plausible_ugm3
from {{ ref('pollutants') }}
where pollutant_code in ({{ "'" ~ var("pollutants") | join("', '") ~ "'" }})
