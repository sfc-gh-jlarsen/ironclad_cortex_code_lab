-- Gap-free daily FX (units per USD) incl. USD=1, forward-filled through today
with currencies as (
    select distinct to_currency as currency_code from {{ ref('stg_ref__fx_rates') }}
    union select 'USD'
),
days as (
    select date_day from {{ ref('dim_date') }}
    where date_day between (select min(rate_date) from {{ ref('stg_ref__fx_rates') }}) and current_date()
),
grid as (
    select d.date_day, c.currency_code from days d cross join currencies c
)
select
    g.date_day                                                               as rate_date,
    g.currency_code,
    iff(g.currency_code = 'USD', 1,
        coalesce(r.units_per_usd,
                 lag(r.units_per_usd) ignore nulls over (partition by g.currency_code order by g.date_day))) as units_per_usd,
    r.units_per_usd is null and g.currency_code <> 'USD'                     as is_forward_filled
from grid g
left join {{ ref('stg_ref__fx_rates') }} r
       on r.rate_date = g.date_day and r.to_currency = g.currency_code
