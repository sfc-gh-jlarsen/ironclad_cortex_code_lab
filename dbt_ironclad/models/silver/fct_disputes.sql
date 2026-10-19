-- Current state of each dispute (latest event wins)
select
    dispute_id,
    ar_document_id,
    billing_doc_id,
    customer_id,
    reason_code,
    dispute_status                                          as current_status,
    disputed_amount,
    credit_amount,
    currency_code,
    owner_team,
    min(event_date) over (partition by dispute_id)          as opened_date,
    iff(dispute_status = 'RESOLVED', event_date, null)      as resolved_date,
    datediff(day, min(event_date) over (partition by dispute_id),
             iff(dispute_status = 'RESOLVED', event_date, current_date())) as days_in_dispute
from {{ ref('stg_collections__dispute_events') }}
qualify row_number() over (partition by dispute_id order by event_at desc) = 1
