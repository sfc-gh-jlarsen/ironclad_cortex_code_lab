{{ config(materialized='view') }}

-- Bronze: WMS_TRANSFER_LANES (wms) -> business-friendly names and types
select
    LANE_ID as lane_id,
    FROM_PLANT as from_plant_id,
    TO_PLANT as to_plant_id,
    DISTANCE_KM::number(10,1) as distance_km,
    MODE as transport_mode,
    TRANSIT_DAYS::int as transit_days,
    COST_PER_KG_USD::number(10,4) as cost_per_kg_usd,
    HANDLING_FEE_USD::number(10,2) as handling_fee_usd
from {{ source('wms', 'WMS_TRANSFER_LANES') }}
qualify row_number() over (partition by LANE_ID order by LANE_ID) = 1
