-- Gold: order-to-cash fulfillment. Grain: sales order line.
-- Links fulfillment outcomes (OTIF, backorders) to downstream disputes and payment behavior.
with ar_by_line as (
    select b.sales_order_line_id,
           max(iff(a.dispute_id is not null, 1, 0)) = 1    as has_dispute,
           max(a.dispute_reason)                           as dispute_reason,
           max(a.days_paid_late)                           as max_days_paid_late,
           sum(a.open_amount_usd * b.net_value / nullif(a.invoice_amount, 0)) as open_ar_usd
    from {{ ref('fct_billing_lines') }} b
    join {{ ref('fct_ar_items') }} a on a.billing_doc_id = b.billing_doc_id
    group by 1
)
select
    s.sales_order_line_id,
    s.sales_order_id,
    s.order_date,
    s.order_type,
    s.customer_id,
    s.company_code,
    s.distribution_channel,
    s.plant_id,
    s.material_id,
    s.requested_delivery_date,
    s.first_goods_issue_date,
    s.last_goods_issue_date,
    s.ordered_qty,
    s.delivered_qty,
    s.ordered_qty - s.delivered_qty                       as undelivered_qty,
    s.net_value_usd,
    s.fill_rate,
    s.delivery_delay_days,
    s.delivery_count,
    s.is_on_time,
    s.is_in_full,
    coalesce(s.is_on_time and s.is_in_full, false)        as is_otif,
    s.fulfillment_status,
    coalesce(ar.has_dispute, false)                       as has_dispute,
    ar.dispute_reason,
    ar.max_days_paid_late,
    round(coalesce(ar.open_ar_usd, 0), 2)                 as open_ar_usd
from {{ ref('fct_sales_order_lines') }} s
left join ar_by_line ar on ar.sales_order_line_id = s.sales_order_line_id
