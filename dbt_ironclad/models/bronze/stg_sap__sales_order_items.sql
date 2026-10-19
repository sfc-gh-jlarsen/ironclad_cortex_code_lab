{{ config(materialized='view') }}

-- Bronze: VBAP (sap) -> business-friendly names and types
select
    VBELN || '-' || LPAD(POSNR, 6, '0') as sales_order_line_id,
    VBELN as sales_order_id,
    POSNR::int as order_item,
    MATNR as material_id,
    WERKS as plant_id,
    KWMENG::number(18,3) as ordered_qty,
    VRKME as uom,
    NETPR::number(18,4) as net_price,
    NETWR::number(18,2) as net_value
from {{ source('sap', 'VBAP') }}
qualify row_number() over (partition by VBELN, POSNR order by VBELN, POSNR) = 1
