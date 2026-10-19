{{ config(materialized='view') }}

-- Bronze: MARC (sap) -> business-friendly names and types
select
    WERKS as plant_id,
    MATNR as material_id,
    MINBE::number(18,3) as reorder_point_qty,
    EISBE::number(18,3) as safety_stock_qty,
    PLIFZ::int as planned_delivery_days,
    DISMM as mrp_type,
    BESKZ as procurement_type
from {{ source('sap', 'MARC') }}
qualify row_number() over (partition by WERKS, MATNR order by WERKS, MATNR) = 1
