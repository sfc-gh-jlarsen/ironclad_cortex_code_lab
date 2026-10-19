-- Sales order line with fulfillment outcome (one row per order line)
with dlv as (
    select i.sales_order_line_id,
           sum(i.delivered_qty)         as delivered_qty,
           min(h.goods_issue_date)      as first_goods_issue_date,
           max(h.goods_issue_date)      as last_goods_issue_date,
           count(distinct i.delivery_id) as delivery_count
    from {{ ref('stg_sap__delivery_items') }} i
    join {{ ref('stg_sap__delivery_headers') }} h on h.delivery_id = i.delivery_id
    group by 1
),
bil as (
    select sales_order_line_id, sum(net_value) as billed_value, sum(billed_qty) as billed_qty
    from {{ ref('stg_sap__billing_items') }}
    group by 1
)
select
    l.sales_order_line_id,
    l.sales_order_id,
    l.order_item,
    h.order_date,
    h.order_type,
    h.customer_id,
    h.sales_org                                                      as company_code,
    h.distribution_channel,
    l.plant_id,
    l.material_id,
    h.requested_delivery_date,
    h.currency_code,
    l.ordered_qty,
    l.net_price,
    l.net_value,
    {{ to_usd('l.net_value') }}                                      as net_value_usd,
    coalesce(d.delivered_qty, 0)                                     as delivered_qty,
    d.first_goods_issue_date,
    d.last_goods_issue_date,
    coalesce(d.delivery_count, 0)                                    as delivery_count,
    coalesce(b.billed_qty, 0)                                        as billed_qty,
    coalesce(b.billed_value, 0)                                      as billed_value,
    datediff(day, h.requested_delivery_date, d.first_goods_issue_date) as delivery_delay_days,
    round(coalesce(d.delivered_qty, 0) / nullif(l.ordered_qty, 0), 4)  as fill_rate,
    d.first_goods_issue_date <= dateadd(day, 2, h.requested_delivery_date) as is_on_time,
    coalesce(d.delivered_qty, 0) >= l.ordered_qty                    as is_in_full,
    case
        when d.delivered_qty is null and current_date() > h.requested_delivery_date then 'Past Due'
        when d.delivered_qty is null then 'Open'
        when d.delivered_qty < l.ordered_qty then 'Backordered'
        else 'Delivered'
    end                                                              as fulfillment_status
from {{ ref('stg_sap__sales_order_items') }} l
join {{ ref('stg_sap__sales_order_headers') }} h on h.sales_order_id = l.sales_order_id
left join {{ ref('fx_rates_daily') }} fx on fx.rate_date = h.order_date and fx.currency_code = h.currency_code
left join dlv d on d.sales_order_line_id = l.sales_order_line_id
left join bil b on b.sales_order_line_id = l.sales_order_line_id
