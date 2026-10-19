{{ config(materialized='view') }}

-- Bronze: EKKO (sap) -> business-friendly names and types
select
    EBELN as po_number,
    BUKRS as company_code,
    BSART as po_type,
    LIFNR as supplier_id,
    EKORG as purchasing_org,
    BEDAT as po_date,
    WAERS as currency_code,
    ERNAM as buyer_id,
    CREATED_TS as created_at
from {{ source('sap', 'EKKO') }}
qualify row_number() over (partition by EBELN order by EBELN) = 1
