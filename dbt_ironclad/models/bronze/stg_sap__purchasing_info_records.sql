{{ config(materialized='view') }}

-- Bronze: EINA (sap) -> business-friendly names and types
select
    INFNR as info_record_id,
    LIFNR as supplier_id,
    MATNR as material_id,
    NETPR_USD::number(18,4) as contract_price_usd,
    APLFZ::int as contract_lead_time_days,
    IS_PRIMARY as is_primary_source,
    VALID_FROM as valid_from,
    VALID_TO as valid_to
from {{ source('sap', 'EINA') }}
qualify row_number() over (partition by INFNR order by INFNR) = 1
