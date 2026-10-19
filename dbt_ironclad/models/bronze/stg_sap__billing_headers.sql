{{ config(materialized='view') }}

-- Bronze: VBRK (sap) -> business-friendly names and types
select
    VBELN as billing_doc_id,
    FKART as billing_type,
    FKDAT as billing_date,
    KUNAG as customer_id,
    BUKRS as company_code,
    NETWR::number(18,2) as net_value,
    WAERK as currency_code,
    ZTERM as payment_terms_code
from {{ source('sap', 'VBRK') }}
qualify row_number() over (partition by VBELN order by VBELN) = 1
