{{ config(materialized='view') }}

-- Bronze: EKPO (sap) -> business-friendly names and types
select
    EBELN || '-' || LPAD(EBELP, 5, '0') as po_line_id,
    EBELN as po_number,
    EBELP::int as po_item,
    MATNR as material_id,
    WERKS as plant_id,
    MENGE::number(18,3) as ordered_qty,
    MEINS as uom,
    NETPR::number(18,4) as net_price,
    NETWR::number(18,2) as net_value,
    EINDT as promised_delivery_date,
    INFNR as info_record_id
from {{ source('sap', 'EKPO') }}
qualify row_number() over (partition by EBELN, EBELP order by EBELN, EBELP) = 1
