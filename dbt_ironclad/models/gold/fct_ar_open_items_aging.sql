-- Gold: open AR items as of the latest loaded business day, with aging buckets
-- Grain: one row per open customer invoice (AR document)
with as_of as (
    select max(invoice_date) as as_of_date from {{ ref('fct_ar_items') }}
)
select
    a.ar_document_id,
    a.billing_doc_id,
    a.customer_id,
    a.company_code,
    a.invoice_date,
    a.due_date,
    o.as_of_date,
    a.currency_code,
    a.invoice_amount                                           as open_amount,
    a.open_amount_usd,
    datediff(day, a.invoice_date, o.as_of_date)                as days_outstanding,
    greatest(datediff(day, a.due_date, o.as_of_date), 0)       as days_past_due,
    case
        when o.as_of_date <= a.due_date                          then '0 Current'
        when datediff(day, a.due_date, o.as_of_date) <= 30       then '1 1-30'
        when datediff(day, a.due_date, o.as_of_date) <= 60       then '2 31-60'
        when datediff(day, a.due_date, o.as_of_date) <= 90       then '3 61-90'
        else '4 90+'
    end                                                        as aging_bucket,
    a.dispute_id is not null and a.dispute_status <> 'RESOLVED' as is_in_active_dispute,
    a.dispute_reason,
    a.dispute_status,
    a.was_delivered_late,
    a.was_short_shipped
from {{ ref('fct_ar_items') }} a
cross join as_of o
where not a.is_cleared
