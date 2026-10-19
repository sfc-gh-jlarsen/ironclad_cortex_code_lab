-- Customer AR item (one per invoice) with clearing, dispute and delivery-performance context
with deliv as (
    select h.delivery_id,
           h.goods_issue_date,
           max(so.requested_delivery_date)                        as requested_delivery_date,
           sum(i.delivered_qty)                                   as delivered_qty,
           max(iff(sol.ordered_qty > sol.delivered_qty or sol.delivery_count > 1, 1, 0)) = 1 as has_short_shipped_line
    from {{ ref('stg_sap__delivery_headers') }} h
    join {{ ref('stg_sap__delivery_items') }} i on i.delivery_id = h.delivery_id
    join {{ ref('stg_sap__sales_order_headers') }} so on so.sales_order_id = i.sales_order_id
    join {{ ref('fct_sales_order_lines') }} sol on sol.sales_order_line_id = i.sales_order_line_id
    group by 1, 2
),
bill_delivery as (
    select distinct billing_doc_id, delivery_id from {{ ref('stg_sap__billing_items') }}
)
select
    a.ar_document_id,
    a.company_code,
    a.customer_id,
    a.billing_doc_id,
    bd.delivery_id,
    a.posting_date                                                   as invoice_date,
    a.due_date,
    a.payment_terms_days,
    a.currency_code,
    a.invoice_amount,
    {{ to_usd('a.invoice_amount') }}                                 as invoice_amount_usd,
    p.payment_id,
    p.payment_date                                                   as cleared_date,
    coalesce(p.payment_amount, 0)                                    as paid_amount,
    p.payment_method,
    d.dispute_id,
    d.reason_code                                                    as dispute_reason,
    d.current_status                                                 as dispute_status,
    coalesce(d.credit_amount, 0)                                     as credit_amount,
    p.payment_id is not null                                         as is_cleared,
    iff(p.payment_id is null, a.invoice_amount, 0)                   as open_amount,
    iff(p.payment_id is null, {{ to_usd('a.invoice_amount') }}, 0)   as open_amount_usd,
    datediff(day, a.posting_date, p.payment_date)                    as days_to_pay,
    datediff(day, a.due_date, p.payment_date)                        as days_paid_late,
    dl.goods_issue_date > dateadd(day, 2, dl.requested_delivery_date) as was_delivered_late,
    dl.has_short_shipped_line                                        as was_short_shipped
from {{ ref('stg_sap__ar_postings') }} a
left join bill_delivery bd on bd.billing_doc_id = a.billing_doc_id
left join deliv dl on dl.delivery_id = bd.delivery_id
left join {{ ref('stg_sap__payments') }} p on p.ar_document_id = a.ar_document_id
left join {{ ref('fct_disputes') }} d on d.ar_document_id = a.ar_document_id
left join {{ ref('fx_rates_daily') }} fx on fx.rate_date = a.posting_date and fx.currency_code = a.currency_code
