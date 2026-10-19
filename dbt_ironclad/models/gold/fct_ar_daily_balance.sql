-- Gold: daily AR balance per customer, used for DSO and AR-trend analysis.
-- Grain: date x customer. DSO should be computed at the aggregate level:
--   DSO = SUM(ar_balance_usd) / (SUM(sales_trailing_90d_usd) / 90)
with bounds as (
    select min(invoice_date) as d0, max(invoice_date) as d1 from {{ ref('fct_ar_items') }}
),
days as (
    select d.date_day from {{ ref('dim_date') }} d, bounds b where d.date_day between b.d0 and b.d1
),
cust as (
    select distinct customer_id, company_code from {{ ref('fct_ar_items') }}
),
balance as (
    select dy.date_day,
           a.customer_id,
           sum(a.invoice_amount_usd)                                                       as ar_balance_usd,
           sum(iff(a.due_date < dy.date_day, a.invoice_amount_usd, 0))                      as overdue_balance_usd,
           sum(iff(datediff(day, a.due_date, dy.date_day) > 60, a.invoice_amount_usd, 0))   as over_60_balance_usd,
           sum(iff(datediff(day, a.due_date, dy.date_day) > 90, a.invoice_amount_usd, 0))   as over_90_balance_usd,
           count(*)                                                                        as open_invoice_count
    from days dy
    join {{ ref('fct_ar_items') }} a
      on a.invoice_date <= dy.date_day
     and (a.cleared_date is null or a.cleared_date > dy.date_day)
    group by 1, 2
),
sales as (
    select dy.date_day, a.customer_id, sum(a.invoice_amount_usd) as sales_trailing_90d_usd
    from days dy
    join {{ ref('fct_ar_items') }} a
      on a.invoice_date > dateadd(day, -90, dy.date_day) and a.invoice_date <= dy.date_day
    group by 1, 2
),
collected as (
    select cleared_date as date_day, customer_id, sum(invoice_amount_usd) as collected_usd
    from {{ ref('fct_ar_items') }} where is_cleared group by 1, 2
)
select
    dy.date_day                                    as balance_date,
    c.customer_id,
    c.company_code,
    coalesce(b.ar_balance_usd, 0)                  as ar_balance_usd,
    coalesce(b.overdue_balance_usd, 0)             as overdue_balance_usd,
    coalesce(b.over_60_balance_usd, 0)             as over_60_balance_usd,
    coalesce(b.over_90_balance_usd, 0)             as over_90_balance_usd,
    coalesce(b.open_invoice_count, 0)              as open_invoice_count,
    coalesce(s.sales_trailing_90d_usd, 0)          as sales_trailing_90d_usd,
    coalesce(cl.collected_usd, 0)                  as collected_usd,
    round(div0null(coalesce(b.ar_balance_usd, 0), coalesce(s.sales_trailing_90d_usd, 0) / 90), 1) as customer_dso_days
from days dy
cross join cust c
left join balance b   on b.date_day = dy.date_day and b.customer_id = c.customer_id
left join sales s     on s.date_day = dy.date_day and s.customer_id = c.customer_id
left join collected cl on cl.date_day = dy.date_day and cl.customer_id = c.customer_id
