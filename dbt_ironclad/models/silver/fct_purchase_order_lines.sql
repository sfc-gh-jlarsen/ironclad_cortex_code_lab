-- Purchase order line with receipt, quality and invoice outcomes (one row per PO line)
with gr as (
    select po_line_id,
           sum(received_qty)        as received_qty,
           min(posting_date)        as first_receipt_date,
           max(posting_date)        as last_receipt_date,
           count(*)                 as receipt_count
    from {{ ref('stg_sap__goods_receipts') }}
    group by 1
),
qi as (
    select po_line_id,
           sum(rejected_qty)                       as rejected_qty,
           count_if(inspection_result <> 'ACCEPT') as failed_inspections,
           count(*)                                as inspections
    from {{ ref('stg_portal__quality_inspections') }}
    group by 1
),
inv as (
    select i.po_line_id,
           sum(i.invoiced_qty)    as invoiced_qty,
           sum(i.invoiced_amount) as invoiced_amount,
           max(h.invoice_date)    as invoice_date,
           max(h.supplier_invoice_id) as supplier_invoice_id
    from {{ ref('stg_sap__supplier_invoice_items') }} i
    join {{ ref('stg_sap__supplier_invoice_headers') }} h on h.supplier_invoice_id = i.supplier_invoice_id
    group by 1
)
select
    l.po_line_id,
    l.po_number,
    l.po_item,
    h.po_date,
    h.company_code,
    h.supplier_id,
    h.buyer_id,
    l.plant_id,
    l.material_id,
    l.info_record_id,
    l.uom,
    h.currency_code,
    l.ordered_qty,
    l.net_price,
    l.net_value,
    {{ to_usd('l.net_value') }}                                         as net_value_usd,
    ir.contract_price_usd,
    round(l.net_price / nullif(fx.units_per_usd, 0), 4)                 as net_price_usd,
    l.promised_delivery_date,
    ir.contract_lead_time_days,
    ir.is_primary_source,
    coalesce(gr.received_qty, 0)                                        as received_qty,
    gr.first_receipt_date,
    gr.last_receipt_date,
    coalesce(gr.receipt_count, 0)                                       as receipt_count,
    datediff(day, l.promised_delivery_date, gr.first_receipt_date)      as receipt_delay_days,
    datediff(day, h.po_date, gr.last_receipt_date)                      as actual_lead_time_days,
    coalesce(qi.rejected_qty, 0)                                        as rejected_qty,
    coalesce(qi.failed_inspections, 0)                                  as failed_inspections,
    coalesce(qi.inspections, 0)                                         as inspections,
    inv.supplier_invoice_id,
    inv.invoice_date,
    coalesce(inv.invoiced_qty, 0)                                       as invoiced_qty,
    coalesce(inv.invoiced_amount, 0)                                    as invoiced_amount,
    case
        when gr.first_receipt_date is null and current_date() > l.promised_delivery_date then 'Overdue'
        when gr.first_receipt_date is null then 'Open'
        when gr.received_qty < l.ordered_qty then 'Partially Received'
        when inv.supplier_invoice_id is null then 'Received - Awaiting Invoice'
        else 'Invoiced'
    end                                                                 as po_line_status,
    gr.first_receipt_date is not null
        and gr.first_receipt_date <= l.promised_delivery_date           as is_on_time,
    gr.received_qty >= l.ordered_qty                                    as is_in_full
from {{ ref('stg_sap__po_items') }} l
join {{ ref('stg_sap__po_headers') }} h on h.po_number = l.po_number
left join {{ ref('fx_rates_daily') }} fx on fx.rate_date = h.po_date and fx.currency_code = h.currency_code
left join {{ ref('stg_sap__purchasing_info_records') }} ir on ir.info_record_id = l.info_record_id
left join gr  on gr.po_line_id = l.po_line_id
left join qi  on qi.po_line_id = l.po_line_id
left join inv on inv.po_line_id = l.po_line_id
