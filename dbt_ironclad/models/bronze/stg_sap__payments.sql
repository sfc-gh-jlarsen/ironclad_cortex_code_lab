{{ config(materialized='view') }}

-- Bronze: PAYMENTS (sap) -> business-friendly names and types
select
    PAYMENT_ID as payment_id,
    BUKRS as company_code,
    KUNNR as customer_id,
    PAYMENT_DATE as payment_date,
    AMOUNT::number(18,2) as payment_amount,
    WAERS as currency_code,
    CLEARED_BELNR as ar_document_id,
    PAYMENT_METHOD as payment_method,
    BANK_REF as bank_reference
from {{ source('sap', 'PAYMENTS') }}
qualify row_number() over (partition by PAYMENT_ID order by PAYMENT_ID) = 1
