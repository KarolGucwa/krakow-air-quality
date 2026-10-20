with spine as (

    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('" ~ var('dim_date_start') ~ "' as date)",
        end_date=dbt.dateadd('day', 2, 'current_date')
    ) }}

),

days as (

    select cast(date_day as date) as date_day from spine

)

select
    date_day,
    cast(extract(year from date_day) as integer)                    as year,
    cast(extract(quarter from date_day) as integer)                 as quarter,
    cast(extract(month from date_day) as integer)                   as month,
    cast(extract(day from date_day) as integer)                     as day_of_month,
    cast({{ iso_day_of_week('date_day') }} as integer)              as iso_day_of_week,
    case cast({{ iso_day_of_week('date_day') }} as integer)
        when 1 then 'Mon' when 2 then 'Tue' when 3 then 'Wed' when 4 then 'Thu'
        when 5 then 'Fri' when 6 then 'Sat' else 'Sun'
    end                                                             as day_name,
    cast({{ iso_day_of_week('date_day') }} as integer) >= 6        as is_weekend,
    {{ season_of_month('extract(month from date_day)') }}           as season,
    extract(month from date_day) in ({{ var('heating_season_months') | join(', ') }}) as is_heating_season,
    {{ heating_season_label('date_day') }}                          as heating_season,
    date_day >= cast('{{ var("ban_effective_date") }}' as date)     as is_after_coal_ban,
    case
        when date_day >= cast('{{ var("ban_effective_date") }}' as date) then 'after ban'
        else 'before ban'
    end                                                             as ban_period
from days
