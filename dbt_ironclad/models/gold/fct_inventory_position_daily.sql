-- Gold: daily inventory position with inbound pipeline (open POs + in-transit transfers as of each day)
-- Grain: snapshot_date x plant x material
with inv as (
    select * from {{ ref('fct_inventory_daily') }}
),
po_line_open as (
    select i.snapshot_date, i.plant_id, i.material_id, p.po_line_id,
           p.ordered_qty - coalesce(sum(g.received_qty), 0) as open_qty
    from inv i
    join {{ ref('fct_purchase_order_lines') }} p
      on p.plant_id = i.plant_id and p.material_id = i.material_id and p.po_date <= i.snapshot_date
    left join {{ ref('fct_goods_receipts') }} g
      on g.po_line_id = p.po_line_id and g.receipt_date <= i.snapshot_date
    group by 1, 2, 3, 4, p.ordered_qty
    having open_qty > 0
),
po_inbound as (
    select snapshot_date, plant_id, material_id, sum(open_qty) as open_po_qty
    from po_line_open
    group by 1, 2, 3
),
tr_inbound as (
    select i.snapshot_date, i.plant_id, i.material_id, sum(t.transfer_qty) as in_transit_transfer_qty
    from inv i
    join {{ ref('fct_stock_transfers') }} t
      on t.to_plant_id = i.plant_id and t.material_id = i.material_id
     and t.ship_date <= i.snapshot_date and coalesce(t.received_date, '9999-12-31') > i.snapshot_date
    group by 1, 2, 3
)
select
    i.*,
    coalesce(po.open_po_qty, 0)                                       as open_po_qty,
    coalesce(tr.in_transit_transfer_qty, 0)                           as in_transit_transfer_qty,
    i.unrestricted_qty + coalesce(po.open_po_qty, 0) + coalesce(tr.in_transit_transfer_qty, 0) as projected_available_qty,
    case
        when i.is_below_safety_stock then 'Critical'
        when i.is_below_reorder_point then 'Below ROP'
        when i.stock_to_rop_ratio > 2.2 then 'Excess'
        else 'Healthy'
    end                                                               as stock_health
from inv i
left join po_inbound po on po.snapshot_date = i.snapshot_date and po.plant_id = i.plant_id and po.material_id = i.material_id
left join tr_inbound tr on tr.snapshot_date = i.snapshot_date and tr.plant_id = i.plant_id and tr.material_id = i.material_id
