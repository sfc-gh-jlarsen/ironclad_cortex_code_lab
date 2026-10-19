"""Read-only SQL against "STREAMLIT-CORTEX-20261018".GOLD for the Collections Cockpit.

Adapted from ar_aging_analysis.sql (queries 1-5). Every statement is a fixed
SELECT with no user input spliced in; filters are applied to the cached
results in pandas, so widget changes never trigger a new query.
"""

GOLD = '"STREAMLIT-CORTEX-20261018".GOLD'

# Filter options.
FILTER_OPTIONS = f"""
SELECT DISTINCT
    a.company_code,
    COALESCE(c.customer_segment, '(unknown)') AS segment
FROM {GOLD}.FCT_AR_OPEN_ITEMS_AGING a
LEFT JOIN {GOLD}.DIM_CUSTOMER c ON c.customer_id = a.customer_id
UNION
SELECT DISTINCT
    b.company_code,
    COALESCE(c.customer_segment, '(unknown)')
FROM {GOLD}.FCT_AR_DAILY_BALANCE b
LEFT JOIN {GOLD}.DIM_CUSTOMER c ON c.customer_id = b.customer_id
ORDER BY 1, 2
"""

# Invoice-level open items (one snapshot). Drives the Open AR / Past due /
# In dispute KPIs, the aging chart, the top-customer table and the drill-down.
OPEN_ITEMS = f"""
SELECT
    a.ar_document_id,
    a.billing_doc_id,
    a.customer_id,
    c.customer_name,
    COALESCE(c.customer_segment, '(unknown)') AS segment,
    a.company_code,
    a.invoice_date,
    a.due_date,
    a.as_of_date,
    a.currency_code,
    a.open_amount,
    a.open_amount_usd,
    a.days_outstanding,
    a.days_past_due,
    a.aging_bucket,
    a.is_in_active_dispute,
    a.dispute_reason,
    a.dispute_status,
    a.was_delivered_late,
    a.was_short_shipped
FROM {GOLD}.FCT_AR_OPEN_ITEMS_AGING a
LEFT JOIN {GOLD}.DIM_CUSTOMER c ON c.customer_id = a.customer_id
"""

# Daily balances summed to date x company code x segment. DSO is computed
# after filtering as SUM(ar) / (SUM(sales_90d) / 90) - never an average of
# CUSTOMER_DSO_DAYS (see the DSO definition in ar_aging_analysis.sql).
DAILY_BALANCE = f"""
SELECT
    b.balance_date,
    b.company_code,
    COALESCE(c.customer_segment, '(unknown)') AS segment,
    SUM(b.ar_balance_usd)         AS ar_usd,
    SUM(b.overdue_balance_usd)    AS overdue_usd,
    SUM(b.sales_trailing_90d_usd) AS sales_90d_usd
FROM {GOLD}.FCT_AR_DAILY_BALANCE b
LEFT JOIN {GOLD}.DIM_CUSTOMER c ON c.customer_id = b.customer_id
GROUP BY 1, 2, 3
"""

# Shipped order lines with fulfillment + dispute + payment flags. Drives the
# Root Cause tab. Open / Past Due lines are excluded: they have IS_ON_TIME =
# NULL but IS_OTIF = FALSE and would understate OTIF. CAUSE is derived here
# from the actual line flags (not the dispute reason code).
FULFILLMENT = f"""
SELECT
    f.sales_order_line_id,
    f.sales_order_id,
    f.customer_id,
    c.customer_name,
    COALESCE(c.customer_segment, '(unknown)') AS segment,
    f.company_code,
    f.order_date,
    f.requested_delivery_date,
    f.first_goods_issue_date,
    f.delivery_delay_days,
    f.fill_rate,
    f.is_on_time,
    f.is_in_full,
    f.is_otif,
    f.fulfillment_status,
    f.has_dispute,
    f.dispute_reason,
    f.max_days_paid_late,
    f.net_value_usd,
    f.open_ar_usd,
    CASE WHEN NOT f.is_on_time AND NOT f.is_in_full THEN 'Late + short'
         WHEN NOT f.is_on_time                      THEN 'Late only'
         WHEN NOT f.is_in_full                      THEN 'Short only'
         ELSE 'OTIF' END AS cause
FROM {GOLD}.FCT_ORDER_FULFILLMENT f
LEFT JOIN {GOLD}.DIM_CUSTOMER c ON c.customer_id = f.customer_id
WHERE f.is_on_time IS NOT NULL
"""
