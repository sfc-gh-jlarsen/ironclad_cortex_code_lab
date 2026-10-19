{{ config(materialized='view') }}

-- Bronze: AR_DISPUTES (collections) -> business-friendly names and types
select
    DISPUTE_ID as dispute_id,
    EVENT_TS as event_at,
    EVENT_TS::date as event_date,
    BELNR as ar_document_id,
    BILLING_DOC as billing_doc_id,
    KUNNR as customer_id,
    REASON_CODE as reason_code,
    STATUS as dispute_status,
    DISPUTED_AMOUNT::number(18,2) as disputed_amount,
    CREDIT_AMOUNT::number(18,2) as credit_amount,
    WAERS as currency_code,
    OWNER as owner_team
from {{ source('collections', 'AR_DISPUTES') }}
qualify row_number() over (partition by DISPUTE_ID, STATUS order by DISPUTE_ID, STATUS) = 1
