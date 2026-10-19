{{ config(materialized='view') }}

-- Bronze: VBAK (sap) -> business-friendly names and types
select
    VBELN as sales_order_id,
    AUART as order_type,
    ERDAT as order_date,
    ERZET as created_at,
    KUNNR as customer_id,
    VKORG as sales_org,
    VTWEG as distribution_channel,
    VDATU as requested_delivery_date,
    WAERK as currency_code,
    NETWR::number(18,2) as net_value,
    BSTNK as customer_po_number
from {{ source('sap', 'VBAK') }}
qualify row_number() over (partition by VBELN order by VBELN) = 1
