{{ config(materialized='view') }}

-- Bronze: T001 (sap) -> business-friendly names and types
select
    BUKRS as company_code,
    BUTXT as company_name,
    LAND1 as country_code,
    WAERS as currency_code
from {{ source('sap', 'T001') }}
qualify row_number() over (partition by BUKRS order by BUKRS) = 1
