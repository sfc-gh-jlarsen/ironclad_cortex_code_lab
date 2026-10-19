-- Supplier invoice line with 3-way match (PO price x received qty vs invoiced)
select
    i.supplier_invoice_line_id,
    i.supplier_invoice_id,
    h.supplier_id,
    h.company_code,
    h.invoice_date,
    h.posting_date,
    h.currency_code,
    h.supplier_reference,
    i.po_line_id,
    i.material_id,
    l.plant_id,
    i.invoiced_qty,
    i.invoiced_amount,
    round(i.invoiced_qty * l.net_price, 2)                                 as expected_amount,
    i.invoiced_amount - round(i.invoiced_qty * l.net_price, 2)             as price_variance_amount,
    {{ to_usd('i.invoiced_amount') }}                                       as invoiced_amount_usd,
    {{ to_usd('i.invoiced_amount - round(i.invoiced_qty * l.net_price, 2)') }} as price_variance_usd,
    abs(i.invoiced_amount - i.invoiced_qty * l.net_price)
        > 0.005 * nullif(i.invoiced_qty * l.net_price, 0)                  as is_match_exception
from {{ ref('stg_sap__supplier_invoice_items') }} i
join {{ ref('stg_sap__supplier_invoice_headers') }} h on h.supplier_invoice_id = i.supplier_invoice_id
join {{ ref('stg_sap__po_items') }} l on l.po_line_id = i.po_line_id
left join {{ ref('fx_rates_daily') }} fx on fx.rate_date = h.invoice_date and fx.currency_code = h.currency_code
