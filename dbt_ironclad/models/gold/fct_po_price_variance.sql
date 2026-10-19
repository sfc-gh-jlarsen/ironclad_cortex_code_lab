-- Gold: purchase price variance - contract vs PO vs invoice. Grain: PO line
with inv as (
    select po_line_id,
           sum(invoiced_amount_usd)  as invoiced_amount_usd,
           sum(price_variance_usd)   as invoice_vs_po_variance_usd,
           max(iff(is_match_exception, 1, 0)) = 1 as has_match_exception
    from {{ ref('fct_supplier_invoice_lines') }}
    group by 1
)
select
    p.po_line_id,
    p.po_number,
    p.po_date,
    p.supplier_id,
    p.plant_id,
    p.material_id,
    p.buyer_id,
    p.is_primary_source,
    p.ordered_qty,
    p.received_qty,
    p.uom,
    p.contract_price_usd,
    p.net_price_usd                                                         as po_price_usd,
    round(div0null(p.net_price_usd - p.contract_price_usd, p.contract_price_usd), 4) as po_vs_contract_pct,
    round((p.net_price_usd - p.contract_price_usd) * p.ordered_qty, 2)      as po_vs_contract_variance_usd,
    p.net_value_usd                                                         as po_value_usd,
    inv.invoiced_amount_usd,
    coalesce(inv.invoice_vs_po_variance_usd, 0)                             as invoice_vs_po_variance_usd,
    coalesce(inv.has_match_exception, false)                                as has_invoice_match_exception,
    p.po_line_status
from {{ ref('fct_purchase_order_lines') }} p
left join inv on inv.po_line_id = p.po_line_id
