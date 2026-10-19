{{ config(materialized='view') }}

-- Bronze: LIKP (sap) -> business-friendly names and types
select
    VBELN as delivery_id,
    LFART as delivery_type,
    VSTEL as plant_id,
    KUNNR as customer_id,
    LFDAT as planned_delivery_date,
    WADAT_IST as goods_issue_date,
    ROUTE as route
from {{ source('sap', 'LIKP') }}
qualify row_number() over (partition by VBELN order by VBELN) = 1
