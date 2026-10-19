-- Conformed date dimension (role-played by order, delivery, due, payment dates in gold)
with spine as (
    select dateadd(day, seq4(), '{{ var("dim_date_start") }}'::date) as date_day
    from table(generator(rowcount => 1100))
)
select
    date_day,
    year(date_day)                                   as calendar_year,
    quarter(date_day)                                as calendar_quarter,
    month(date_day)                                  as calendar_month,
    monthname(date_day)                              as month_name,
    date_trunc('month', date_day)                    as month_start_date,
    date_trunc('week', date_day)                     as week_start_date,
    weekofyear(date_day)                             as iso_week,
    dayofweekiso(date_day)                           as day_of_week_iso,
    dayname(date_day)                                as day_name,
    dayofweekiso(date_day) between 1 and 5           as is_business_day,
    year(date_day) || '-Q' || quarter(date_day)      as year_quarter_label,
    to_char(date_day, 'YYYY-MM')                     as year_month_label
from spine
where date_day <= '{{ var("dim_date_end") }}'::date
