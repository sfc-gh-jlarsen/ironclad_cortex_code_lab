select
    t.transfer_id,
    t.created_at,
    t.ship_date,
    t.from_plant_id,
    t.to_plant_id,
    t.material_id,
    t.transfer_qty,
    t.uom,
    t.lane_id,
    ln.transport_mode,
    ln.transit_days                                       as planned_transit_days,
    t.planned_arrival_date,
    r.received_date,
    r.received_qty,
    r.condition_code,
    datediff(day, t.ship_date, r.received_date)            as actual_transit_days,
    t.freight_cost_usd,
    t.requested_by,
    iff(r.receipt_id is null, 'In Transit', 'Received')   as transfer_status
from {{ ref('stg_wms__transfers') }} t
left join {{ ref('stg_wms__transfer_receipts') }} r on r.transfer_id = t.transfer_id
left join {{ ref('stg_wms__lanes') }} ln on ln.lane_id = t.lane_id
