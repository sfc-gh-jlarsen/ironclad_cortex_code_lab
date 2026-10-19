-- Gold: monthly supplier scorecard. Grain: month x supplier x plant
with po as (
    select date_trunc('month', po_date) as month_start_date, supplier_id, plant_id,
           count(*)                                         as po_lines,
           sum(net_value_usd)                               as spend_usd,
           count_if(receipt_count > 0)                      as received_lines,
           count_if(is_on_time)                             as on_time_lines,
           count_if(is_in_full)                             as in_full_lines,
           count_if(is_on_time and is_in_full)              as otif_lines,
           count_if(po_line_status = 'Overdue')             as overdue_open_lines,
           sum(iff(receipt_count > 0, receipt_delay_days, null)) as total_delay_days,
           sum(received_qty)                                as received_qty,
           sum(rejected_qty)                                as rejected_qty,
           sum(iff(receipt_count > 0, actual_lead_time_days, null)) as total_lead_time_days,
           avg(contract_lead_time_days)                     as avg_contract_lead_time_days
    from {{ ref('fct_purchase_order_lines') }}
    group by 1, 2, 3
),
inv as (
    select date_trunc('month', invoice_date) as month_start_date, supplier_id, plant_id,
           count(*)                       as invoice_lines,
           count_if(is_match_exception)   as invoice_exceptions,
           sum(price_variance_usd)        as invoice_price_variance_usd
    from {{ ref('fct_supplier_invoice_lines') }}
    group by 1, 2, 3
),
risk as (
    select date_trunc('month', score_date) as month_start_date, supplier_id,
           avg(overall_risk_score) as avg_risk_score, avg(delivery_score) as avg_delivery_risk_score
    from {{ ref('stg_risk__supplier_risk_scores') }}
    group by 1, 2
)
select
    po.month_start_date,
    po.supplier_id,
    po.plant_id,
    po.po_lines,
    po.spend_usd,
    po.received_lines,
    po.on_time_lines,
    po.in_full_lines,
    po.otif_lines,
    po.overdue_open_lines,
    -- overdue-but-unreceived lines count as late, otherwise recent months look artificially good
    round(div0null(po.on_time_lines, po.received_lines + po.overdue_open_lines), 4) as on_time_rate,
    round(div0null(po.otif_lines, po.received_lines + po.overdue_open_lines), 4)    as otif_rate,
    round(div0null(po.total_delay_days, po.received_lines), 2)     as avg_receipt_delay_days,
    round(div0null(po.total_lead_time_days, po.received_lines), 1) as avg_actual_lead_time_days,
    round(po.avg_contract_lead_time_days, 1)                       as avg_contract_lead_time_days,
    po.received_qty,
    po.rejected_qty,
    round(div0null(po.rejected_qty, po.received_qty), 4)           as quality_reject_rate,
    coalesce(inv.invoice_lines, 0)                                 as invoice_lines,
    coalesce(inv.invoice_exceptions, 0)                            as invoice_exceptions,
    coalesce(inv.invoice_price_variance_usd, 0)                    as invoice_price_variance_usd,
    round(r.avg_risk_score, 1)                                     as avg_risk_score,
    round(r.avg_delivery_risk_score, 1)                            as avg_delivery_risk_score
from po
left join inv on inv.month_start_date = po.month_start_date and inv.supplier_id = po.supplier_id and inv.plant_id = po.plant_id
left join risk r on r.month_start_date = po.month_start_date and r.supplier_id = po.supplier_id
