{{ config(materialized='view') }}

-- Bronze: VBRP (sap) -> business-friendly names and types
select
    VBELN || '-' || LPAD(POSNR, 6, '0') as billing_line_id,
    VBELN as billing_doc_id,
    POSNR::int as billing_item,
    VGBEL || '-' || LPAD(VGPOS, 6, '0') as delivery_line_id,
    VGBEL as delivery_id,
    AUBEL || '-' || LPAD(AUPOS, 6, '0') as sales_order_line_id,
    AUBEL as sales_order_id,
    MATNR as material_id,
    WERKS as plant_id,
    FKIMG::number(18,3) as billed_qty,
    NETWR::number(18,2) as net_value
from {{ source('sap', 'VBRP') }}
qualify row_number() over (partition by VBELN, POSNR order by VBELN, POSNR) = 1
