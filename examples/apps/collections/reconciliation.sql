-- Collections Cockpit - KPI reconciliation against GOLD
-- Read-only. Compare these numbers to the app's KPI tiles.
-- Source: "STREAMLIT-CORTEX-20261018".GOLD

-- 1) KPI totals: overall (ALL / ALL) and per company code x segment.
--    Open AR / Past due / In dispute come from the open-items snapshot;
--    DSO is aggregate-level on the latest balance date.
WITH items AS (
    SELECT a.company_code,
           COALESCE(c.customer_segment, '(unknown)') AS segment,
           a.open_amount_usd, a.days_past_due, a.is_in_active_dispute
    FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_OPEN_ITEMS_AGING a
    LEFT JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_CUSTOMER c ON c.customer_id = a.customer_id
),
bal AS (
    SELECT b.company_code,
           COALESCE(c.customer_segment, '(unknown)') AS segment,
           b.ar_balance_usd, b.sales_trailing_90d_usd
    FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_DAILY_BALANCE b
    LEFT JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_CUSTOMER c ON c.customer_id = b.customer_id
    WHERE b.balance_date = (SELECT MAX(balance_date) FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_DAILY_BALANCE)
),
kpi_items AS (
    SELECT COALESCE(company_code, 'ALL') AS company_code,
           COALESCE(segment, 'ALL')      AS segment,
           ROUND(SUM(open_amount_usd), 2)                                AS open_ar_usd,
           ROUND(SUM(IFF(days_past_due > 0, open_amount_usd, 0)), 2)     AS past_due_usd,
           ROUND(SUM(IFF(is_in_active_dispute, open_amount_usd, 0)), 2)  AS in_dispute_usd,
           COUNT(*)                                                      AS open_invoices
    FROM items
    GROUP BY GROUPING SETS ((), (company_code, segment))
),
kpi_dso AS (
    SELECT COALESCE(company_code, 'ALL') AS company_code,
           COALESCE(segment, 'ALL')      AS segment,
           ROUND(DIV0NULL(SUM(ar_balance_usd), SUM(sales_trailing_90d_usd) / 90), 1) AS dso_days
    FROM bal
    GROUP BY GROUPING SETS ((), (company_code, segment))
)
SELECT COALESCE(i.company_code, d.company_code) AS company_code,
       COALESCE(i.segment, d.segment)           AS segment,
       i.open_ar_usd, i.past_due_usd, d.dso_days, i.in_dispute_usd, i.open_invoices
FROM kpi_items i
FULL OUTER JOIN kpi_dso d ON d.company_code = i.company_code AND d.segment = i.segment
ORDER BY (company_code = 'ALL') DESC, company_code, segment;

-- 2) Internal consistency checks (every DIFF column should be 0).
WITH items AS (
    SELECT * FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_OPEN_ITEMS_AGING
),
buckets AS (
    SELECT aging_bucket, SUM(open_amount_usd) AS usd FROM items GROUP BY 1
),
cust AS (
    SELECT customer_id, SUM(open_amount_usd) AS usd FROM items WHERE days_past_due > 0 GROUP BY 1
)
SELECT
    ROUND((SELECT SUM(usd) FROM buckets) - (SELECT SUM(open_amount_usd) FROM items), 2)            AS diff_buckets_vs_open_ar,
    ROUND((SELECT SUM(usd) FROM cust) - (SELECT SUM(open_amount_usd) FROM items WHERE days_past_due > 0), 2)
                                                                                                  AS diff_customers_vs_past_due,
    (SELECT COUNT(*) FROM items a
       LEFT JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_CUSTOMER c ON c.customer_id = a.customer_id
     WHERE c.customer_id IS NULL)                                                                  AS items_without_customer,
    (SELECT COUNT(*) - COUNT(DISTINCT ar_document_id) FROM items)                                  AS duplicate_documents,
    (SELECT COUNT(*) FROM items WHERE is_in_active_dispute IS NULL)                                AS null_dispute_flags;

-- 3) Top 10 past-due customers (matches the app table with no filters).
SELECT a.customer_id, c.customer_name,
       COALESCE(c.customer_segment, '(unknown)') AS segment,
       COUNT(*)                                  AS past_due_invoices,
       ROUND(SUM(a.open_amount_usd), 2)          AS past_due_usd,
       MAX(a.days_past_due)                      AS max_days_past_due,
       ROUND(SUM(IFF(a.is_in_active_dispute, a.open_amount_usd, 0)), 2) AS disputed_usd
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_OPEN_ITEMS_AGING a
LEFT JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_CUSTOMER c ON c.customer_id = a.customer_id
WHERE a.days_past_due > 0
GROUP BY 1, 2, 3
ORDER BY past_due_usd DESC
LIMIT 10;

-- ===================== Root Cause tab =====================
-- Shipped order lines only (IS_ON_TIME IS NOT NULL), same as queries.FULFILLMENT.

-- 4) Root Cause KPI tiles (no filters).
SELECT
    ROUND(100 * COUNT_IF(is_otif AND has_dispute)     / NULLIF(COUNT_IF(is_otif), 0), 1)     AS dispute_rate_otif_pct,
    ROUND(100 * COUNT_IF(NOT is_otif AND has_dispute) / NULLIF(COUNT_IF(NOT is_otif), 0), 1) AS dispute_rate_late_short_pct,
    ROUND(100 * COUNT_IF(has_dispute AND is_otif)     / NULLIF(COUNT_IF(has_dispute), 0), 1) AS otif_pct_disputed,
    ROUND(100 * COUNT_IF(NOT has_dispute AND is_otif) / NULLIF(COUNT_IF(NOT has_dispute), 0), 1) AS otif_pct_not_disputed,
    ROUND(AVG(IFF(has_dispute, max_days_paid_late, NULL)), 1)                                AS avg_days_paid_late_disputed,
    ROUND(AVG(IFF(NOT has_dispute, max_days_paid_late, NULL)), 1)                            AS avg_days_paid_late_not_disputed,
    COUNT(*)                                                                                 AS shipped_lines
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_ORDER_FULFILLMENT
WHERE is_on_time IS NOT NULL;

-- 5) Dispute rate by cause (matches the cause chart).
SELECT
    CASE WHEN NOT is_on_time AND NOT is_in_full THEN 'Late + short'
         WHEN NOT is_on_time                    THEN 'Late only'
         WHEN NOT is_in_full                    THEN 'Short only'
         ELSE 'OTIF' END                                  AS cause,
    COUNT(*)                                              AS lines,
    COUNT_IF(has_dispute)                                 AS disputed,
    ROUND(100 * COUNT_IF(has_dispute) / COUNT(*), 1)      AS dispute_rate_pct
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_ORDER_FULFILLMENT
WHERE is_on_time IS NOT NULL
GROUP BY 1
ORDER BY dispute_rate_pct DESC;

-- 6) Dispute reasons (matches the reasons chart).
SELECT dispute_reason,
       COUNT(*)                                          AS lines,
       ROUND(100 * RATIO_TO_REPORT(COUNT(*)) OVER (), 1) AS share_pct,
       ROUND(SUM(net_value_usd))                         AS value_usd,
       ROUND(AVG(max_days_paid_late), 1)                 AS avg_days_paid_late
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_ORDER_FULFILLMENT
WHERE is_on_time IS NOT NULL AND has_dispute
GROUP BY 1
ORDER BY lines DESC;

-- 7) Consistency: no shipped line should be double counted or lack a customer.
SELECT
    COUNT(*) - COUNT(DISTINCT sales_order_line_id)                       AS duplicate_lines,
    COUNT_IF(c.customer_id IS NULL)                                      AS lines_without_customer,
    COUNT_IF(f.has_dispute IS NULL OR f.is_otif IS NULL)                 AS null_flags
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_ORDER_FULFILLMENT f
LEFT JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_CUSTOMER c ON c.customer_id = f.customer_id
WHERE f.is_on_time IS NOT NULL;
