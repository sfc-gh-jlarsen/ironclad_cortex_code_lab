{{ config(materialized='view') }}

-- Bronze: LIPS (sap) -> business-friendly names and types
select
    VBELN || '-' || LPAD(POSNR, 6, '0') as delivery_line_id,
    VBELN as delivery_id,
    POSNR::int as delivery_item,
    VGBEL || '-' || LPAD(VGPOS, 6, '0') as sales_order_line_id,
    VGBEL as sales_order_id,
    MATNR as material_id,
    WERKS as plant_id,
    LFIMG::number(18,3) as delivered_qty,
    VRKME as uom
from {{ source('sap', 'LIPS') }}
qualify row_number() over (partition by VBELN, POSNR order by VBELN, POSNR) = 1
