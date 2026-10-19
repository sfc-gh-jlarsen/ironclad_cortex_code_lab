{{ config(materialized='view') }}

-- Bronze: LFA1 (sap) -> business-friendly names and types
select
    LIFNR as supplier_id,
    NAME1 as supplier_name,
    LAND1 as country_code,
    ORT01 as city,
    KTOKK as account_group,
    PRIMARY_CATEGORY as primary_category
from {{ source('sap', 'LFA1') }}
qualify row_number() over (partition by LIFNR order by LIFNR) = 1
