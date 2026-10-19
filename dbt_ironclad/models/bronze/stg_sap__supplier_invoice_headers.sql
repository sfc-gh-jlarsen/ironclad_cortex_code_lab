{{ config(materialized='view') }}

-- Bronze: RBKP (sap) -> business-friendly names and types
select
    BELNR as supplier_invoice_id,
    GJAHR::int as fiscal_year,
    BUKRS as company_code,
    LIFNR as supplier_id,
    BLDAT as invoice_date,
    BUDAT as posting_date,
    RMWWR::number(18,2) as gross_amount,
    WAERS as currency_code,
    XBLNR as supplier_reference,
    ZTERM as payment_terms_code
from {{ source('sap', 'RBKP') }}
qualify row_number() over (partition by BELNR order by BELNR) = 1
