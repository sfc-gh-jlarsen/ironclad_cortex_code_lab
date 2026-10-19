-- Goods receipt grain, joined to its quality inspection
select
    g.material_document,
    g.po_line_id,
    g.po_number,
    h.supplier_id,
    l.plant_id,
    l.material_id,
    g.posting_date                     as receipt_date,
    g.received_qty,
    g.received_value,
    g.currency_code,
    {{ to_usd('g.received_value') }}   as received_value_usd,
    q.inspection_lot_id,
    q.inspection_result,
    coalesce(q.rejected_qty, 0)        as rejected_qty,
    q.primary_defect_code,
    q.inspector_id
from {{ ref('stg_sap__goods_receipts') }} g
join {{ ref('stg_sap__po_items') }} l   on l.po_line_id = g.po_line_id
join {{ ref('stg_sap__po_headers') }} h on h.po_number = g.po_number
left join {{ ref('stg_portal__quality_inspections') }} q on q.material_document = g.material_document
left join {{ ref('fx_rates_daily') }} fx on fx.rate_date = g.posting_date and fx.currency_code = g.currency_code
