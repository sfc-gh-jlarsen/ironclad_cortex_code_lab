-- Billing line (invoice item) linked back to the delivery and order line
select
    b.billing_line_id,
    b.billing_doc_id,
    h.billing_date,
    h.customer_id,
    h.company_code,
    b.delivery_id,
    b.delivery_line_id,
    b.sales_order_id,
    b.sales_order_line_id,
    b.material_id,
    b.plant_id,
    b.billed_qty,
    b.net_value,
    h.currency_code,
    {{ to_usd('b.net_value') }}           as net_value_usd
from {{ ref('stg_sap__billing_items') }} b
join {{ ref('stg_sap__billing_headers') }} h on h.billing_doc_id = b.billing_doc_id
left join {{ ref('fx_rates_daily') }} fx on fx.rate_date = h.billing_date and fx.currency_code = h.currency_code
