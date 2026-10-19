{{ config(materialized='view') }}

-- Bronze: BSID_BSAD (sap) -> business-friendly names and types
select
    BELNR as ar_document_id,
    BUKRS as company_code,
    GJAHR::int as fiscal_year,
    KUNNR as customer_id,
    BLART as document_type,
    BSCHL as posting_key,
    BUDAT as posting_date,
    ZFBDT as baseline_date,
    ZBD1T::int as payment_terms_days,
    DATEADD(day, ZBD1T, ZFBDT) as due_date,
    DMBTR::number(18,2) as invoice_amount,
    WAERS as currency_code,
    VBELN as billing_doc_id
from {{ source('sap', 'BSID_BSAD') }}
qualify row_number() over (partition by BELNR order by BELNR) = 1
