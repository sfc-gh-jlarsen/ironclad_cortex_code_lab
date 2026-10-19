{{ config(materialized='view') }}

-- Bronze: T001W (sap) -> business-friendly names and types
select
    WERKS as plant_id,
    NAME1 as plant_name,
    ORT01 as city,
    REGIO as region,
    LAND1 as country_code,
    BUKRS as company_code,
    LAT as latitude,
    LON as longitude
from {{ source('sap', 'T001W') }}
qualify row_number() over (partition by WERKS order by WERKS) = 1
