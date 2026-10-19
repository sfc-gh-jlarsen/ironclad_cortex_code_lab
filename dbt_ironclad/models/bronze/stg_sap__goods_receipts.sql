{{ config(materialized='view') }}

-- Bronze: EKBE (sap) -> business-friendly names and types
select
    BELNR as material_document,
    GJAHR::int as fiscal_year,
    EBELN || '-' || LPAD(EBELP, 5, '0') as po_line_id,
    EBELN as po_number,
    EBELP::int as po_item,
    BWART as movement_type,
    BUDAT as posting_date,
    MENGE::number(18,3) as received_qty,
    DMBTR::number(18,2) as received_value,
    WAERS as currency_code
from {{ source('sap', 'EKBE') }}
qualify row_number() over (partition by BELNR order by BELNR) = 1
