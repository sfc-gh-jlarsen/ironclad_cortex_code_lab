{{ config(materialized='view') }}

-- Bronze: WMS_STOCK_TRANSFERS (wms) -> business-friendly names and types
select
    TRANSFER_ID as transfer_id,
    CREATED_TS as created_at,
    FROM_PLANT as from_plant_id,
    TO_PLANT as to_plant_id,
    MATERIAL_ID as material_id,
    QUANTITY::number(18,3) as transfer_qty,
    UOM as uom,
    LANE_ID as lane_id,
    SHIP_DATE as ship_date,
    PLANNED_ARRIVAL_DATE as planned_arrival_date,
    FREIGHT_COST_USD::number(18,2) as freight_cost_usd,
    REQUESTED_BY as requested_by
from {{ source('wms', 'WMS_STOCK_TRANSFERS') }}
qualify row_number() over (partition by TRANSFER_ID order by TRANSFER_ID) = 1
