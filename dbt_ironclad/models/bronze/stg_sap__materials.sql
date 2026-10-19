{{ config(materialized='view') }}

-- Bronze: MARA (sap) -> business-friendly names and types
select
    MATNR as material_id,
    MAKTX as material_description,
    MATKL as material_group,
    MTART as material_type,
    MEINS as base_uom,
    BASE_PRICE_USD::number(18,4) as list_price_usd,
    NTGEW_KG::number(18,3) as net_weight_kg,
    NULLIF(PRODUCT_LINE, '') as product_line,
    NULLIF(TIRE_SIZE, '') as tire_size
from {{ source('sap', 'MARA') }}
qualify row_number() over (partition by MATNR order by MATNR) = 1
