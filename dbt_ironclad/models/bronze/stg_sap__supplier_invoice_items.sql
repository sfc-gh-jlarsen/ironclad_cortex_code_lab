{{ config(materialized='view') }}

-- Bronze: RSEG (sap) -> business-friendly names and types
select
    BELNR || '-' || LPAD(BUZEI, 4, '0') as supplier_invoice_line_id,
    BELNR as supplier_invoice_id,
    BUZEI::int as invoice_item,
    EBELN || '-' || LPAD(EBELP, 5, '0') as po_line_id,
    MATNR as material_id,
    MENGE::number(18,3) as invoiced_qty,
    WRBTR::number(18,2) as invoiced_amount
from {{ source('sap', 'RSEG') }}
qualify row_number() over (partition by BELNR, BUZEI order by BELNR, BUZEI) = 1
