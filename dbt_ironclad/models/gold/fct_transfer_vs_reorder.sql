-- Gold: transfer-vs-reorder decision support.
-- For every day a raw material is below its reorder point at a plant, compare
--   (a) transferring surplus from the cheapest sister plant, vs
--   (b) buying from the primary contracted supplier,
-- and record what the business actually did that day (PO, transfer, nothing).
-- Grain: snapshot_date x plant x material (only below-ROP raw materials)
with needs as (
    select i.snapshot_date, i.plant_id, i.material_id, i.uom, i.unrestricted_qty, i.reorder_point_qty,
           i.safety_stock_qty,
           i.reorder_point_qty + i.safety_stock_qty - i.unrestricted_qty  as needed_qty
    from {{ ref('fct_inventory_daily') }} i
    join {{ ref('dim_material') }} m on m.material_id = i.material_id
    where i.is_below_reorder_point and m.material_type = 'ROH'
),
donors as (
    select n.snapshot_date, n.plant_id, n.material_id,
           d.plant_id                                                         as donor_plant_id,
           d.surplus_above_1_5x_rop_qty                                       as donor_surplus_qty,
           l.transit_days,
           l.transport_mode,
           least(n.needed_qty, d.surplus_above_1_5x_rop_qty)                  as transferable_qty,
           round(least(n.needed_qty, d.surplus_above_1_5x_rop_qty) * m.net_weight_kg * l.cost_per_kg_usd
                 + l.handling_fee_usd, 2)                                     as transfer_cost_usd
    from needs n
    join {{ ref('fct_inventory_daily') }} d
      on d.snapshot_date = n.snapshot_date and d.material_id = n.material_id
     and d.plant_id <> n.plant_id and d.surplus_above_1_5x_rop_qty > 0
    join {{ ref('stg_wms__lanes') }} l on l.from_plant_id = d.plant_id and l.to_plant_id = n.plant_id
    join {{ ref('dim_material') }} m on m.material_id = n.material_id
    qualify row_number() over (partition by n.snapshot_date, n.plant_id, n.material_id
                               order by least(n.needed_qty, d.surplus_above_1_5x_rop_qty) >= 0.5 * n.needed_qty desc,
                                        l.transit_days, transfer_cost_usd) = 1
),
supplier as (
    select material_id, supplier_id, contract_price_usd, contract_lead_time_days
    from {{ ref('stg_sap__purchasing_info_records') }}
    where is_primary_source
),
actions as (
    select po_date as action_date, plant_id, material_id, 'PO' as action_type, sum(ordered_qty) as action_qty
    from {{ ref('fct_purchase_order_lines') }} group by 1, 2, 3
    union all
    select ship_date, to_plant_id, material_id, 'TRANSFER', sum(transfer_qty)
    from {{ ref('fct_stock_transfers') }} group by 1, 2, 3
),
actions_day as (
    select action_date, plant_id, material_id,
           max(iff(action_type = 'TRANSFER', 1, 0)) = 1 as transfer_created,
           max(iff(action_type = 'PO', 1, 0)) = 1       as po_created
    from actions group by 1, 2, 3
)
select
    n.snapshot_date,
    n.plant_id,
    n.material_id,
    n.uom,
    n.unrestricted_qty,
    n.reorder_point_qty,
    n.needed_qty,
    s.supplier_id                                                  as primary_supplier_id,
    s.contract_lead_time_days                                      as reorder_lead_time_days,
    round(n.needed_qty * s.contract_price_usd, 2)                  as reorder_cost_usd,
    d.donor_plant_id,
    d.donor_surplus_qty,
    d.transferable_qty,
    d.transport_mode,
    d.transit_days                                                 as transfer_lead_time_days,
    d.transfer_cost_usd,
    s.contract_lead_time_days - d.transit_days                     as days_saved_by_transfer,
    round(d.transferable_qty * s.contract_price_usd - d.transfer_cost_usd, 2) as working_capital_avoided_usd,
    case
        when d.donor_plant_id is not null
         and d.transferable_qty >= 0.5 * n.needed_qty
         and d.transit_days < s.contract_lead_time_days
         and d.transfer_cost_usd < 0.25 * d.transferable_qty * s.contract_price_usd
        then 'TRANSFER'
        else 'REORDER'
    end                                                            as recommended_action,
    case when coalesce(a.transfer_created, false) then 'TRANSFER'
         when coalesce(a.po_created, false) then 'PO'
         else 'NONE' end                                           as actual_action
from needs n
left join donors d   on d.snapshot_date = n.snapshot_date and d.plant_id = n.plant_id and d.material_id = n.material_id
left join supplier s on s.material_id = n.material_id
left join actions_day a on a.action_date = n.snapshot_date and a.plant_id = n.plant_id and a.material_id = n.material_id
