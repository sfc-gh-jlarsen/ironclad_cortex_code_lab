{{ config(materialized='view') }}

-- Bronze: MARD (sap) -> business-friendly names and types
select
    SNAPSHOT_DATE as snapshot_date,
    WERKS as plant_id,
    MATNR as material_id,
    LGORT as storage_location,
    LABST::number(18,3) as unrestricted_qty,
    INSME::number(18,3) as quality_inspection_qty,
    MEINS as uom
from {{ source('sap', 'MARD') }}
qualify row_number() over (partition by SNAPSHOT_DATE, WERKS, MATNR order by SNAPSHOT_DATE, WERKS, MATNR) = 1
