{{ config(
    materialized='incremental',
    unique_key=['snapshot_date', 'plant_id', 'material_id'],
    incremental_strategy='merge',
    on_schema_change='sync_all_columns'
) }}
-- Daily inventory position vs. reorder point (incremental: snapshots are immutable once loaded)
select
    s.snapshot_date,
    s.plant_id,
    s.material_id,
    s.uom,
    s.unrestricted_qty,
    s.quality_inspection_qty,
    mp.reorder_point_qty,
    mp.safety_stock_qty,
    mp.procurement_type,
    round(s.unrestricted_qty / nullif(mp.reorder_point_qty, 0), 3)        as stock_to_rop_ratio,
    s.unrestricted_qty < mp.reorder_point_qty                              as is_below_reorder_point,
    s.unrestricted_qty < mp.safety_stock_qty                               as is_below_safety_stock,
    greatest(mp.reorder_point_qty - s.unrestricted_qty, 0)                 as shortfall_to_rop_qty,
    greatest(s.unrestricted_qty - 1.5 * mp.reorder_point_qty, 0)           as surplus_above_1_5x_rop_qty,
    round(s.unrestricted_qty * m.list_price_usd, 2)                        as inventory_value_usd
from {{ ref('stg_sap__inventory_snapshots') }} s
join {{ ref('stg_sap__material_plant') }} mp on mp.plant_id = s.plant_id and mp.material_id = s.material_id
join {{ ref('stg_sap__materials') }} m on m.material_id = s.material_id
{% if is_incremental() %}
where s.snapshot_date > (select dateadd(day, -3, max(snapshot_date)) from {{ this }})
{% endif %}
