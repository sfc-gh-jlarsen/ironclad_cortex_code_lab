{{ config(materialized='view') }}

-- Bronze: WMS_TRANSFER_RECEIPTS (wms) -> business-friendly names and types
select
    RECEIPT_ID as receipt_id,
    TRANSFER_ID as transfer_id,
    TO_PLANT as to_plant_id,
    RECEIVED_DATE as received_date,
    RECEIVED_QTY::number(18,3) as received_qty,
    CONDITION_CODE as condition_code
from {{ source('wms', 'WMS_TRANSFER_RECEIPTS') }}
qualify row_number() over (partition by RECEIPT_ID order by RECEIPT_ID) = 1
