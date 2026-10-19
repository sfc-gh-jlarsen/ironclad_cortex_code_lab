-- AR receivables health check
-- Source: "STREAMLIT-CORTEX-20261018".GOLD

-- 1) Open AR by aging bucket, with disputed amounts
SELECT
    aging_bucket,
    COUNT(*)                                               AS open_invoices,
    ROUND(SUM(open_amount_usd))                            AS open_usd,
    ROUND(SUM(IFF(is_in_active_dispute, open_amount_usd, 0))) AS disputed_usd,
    MAX(as_of_date)                                        AS as_of
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_OPEN_ITEMS_AGING
GROUP BY aging_bucket
ORDER BY aging_bucket;

-- 2) Month-end AR balance, overdue share, and DSO trend
WITH daily AS (
    SELECT
        balance_date,
        SUM(ar_balance_usd)         AS ar,
        SUM(overdue_balance_usd)    AS overdue,
        SUM(over_90_balance_usd)    AS over_90,
        SUM(sales_trailing_90d_usd) AS sales_90d
    FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_DAILY_BALANCE
    GROUP BY balance_date
)
SELECT
    balance_date,
    ROUND(ar)                                   AS ar_usd,
    ROUND(overdue)                              AS overdue_usd,
    ROUND(100 * overdue / NULLIF(ar, 0), 1)     AS pct_overdue,
    ROUND(over_90)                              AS over_90_usd,
    ROUND(ar / NULLIF(sales_90d, 0) * 90, 1)    AS dso_days
FROM daily
QUALIFY balance_date = MAX(balance_date) OVER (PARTITION BY DATE_TRUNC('month', balance_date))
ORDER BY balance_date;

-- 3) Top 10 customers by past-due balance, with disputed share
SELECT
    a.customer_id,
    c.customer_name,
    c.customer_segment,
    COUNT(*)                                                    AS past_due_invoices,
    ROUND(SUM(a.open_amount_usd))                               AS past_due_usd,
    MAX(a.days_past_due)                                        AS max_days_past_due,
    ROUND(SUM(IFF(a.is_in_active_dispute, a.open_amount_usd, 0))) AS disputed_usd,
    ROUND(100 * SUM(IFF(a.is_in_active_dispute, a.open_amount_usd, 0))
              / NULLIF(SUM(a.open_amount_usd), 0), 1)           AS pct_disputed
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_OPEN_ITEMS_AGING a
LEFT JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_CUSTOMER c
    ON c.customer_id = a.customer_id
WHERE a.days_past_due > 0
GROUP BY a.customer_id, c.customer_name, c.customer_segment
ORDER BY past_due_usd DESC
LIMIT 10;

-- 4) Past-due balance in active dispute, by reason
SELECT
    COALESCE(dispute_reason, '(none)') AS dispute_reason,
    COUNT(*)                           AS invoices,
    ROUND(SUM(open_amount_usd))        AS disputed_past_due_usd
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_OPEN_ITEMS_AGING
WHERE days_past_due > 0
  AND is_in_active_dispute
GROUP BY 1
ORDER BY disputed_past_due_usd DESC;

-- DSO definition (from the GOLD.FCT_AR_DAILY_BALANCE build):
--   DSO = SUM(ar_balance_usd) / (SUM(sales_trailing_90d_usd) / 90)
--   ar_balance_usd = full invoice amount of items not yet cleared on that date
--   sales_trailing_90d_usd = invoices dated in the 90 days up to that date
-- Compute at the aggregate level; do not average CUSTOMER_DSO_DAYS.
-- Note: history starts 2026-07-23, so DSO reads ~90 until the book matures.

-- 5) Weekly DSO and overdue share by customer segment, last 90 days
WITH max_dt AS (
    SELECT MAX(balance_date) AS d FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_DAILY_BALANCE
)
SELECT
    b.balance_date,
    COALESCE(c.customer_segment, '(unknown)')                                  AS segment,
    COUNT(DISTINCT b.customer_id)                                              AS customers,
    ROUND(SUM(b.ar_balance_usd))                                               AS ar_usd,
    ROUND(DIV0NULL(SUM(b.ar_balance_usd), SUM(b.sales_trailing_90d_usd) / 90), 1) AS dso_days,
    ROUND(100 * DIV0NULL(SUM(b.overdue_balance_usd), SUM(b.ar_balance_usd)), 1)  AS pct_overdue
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_DAILY_BALANCE b
CROSS JOIN max_dt m
LEFT JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_CUSTOMER c
    ON c.customer_id = b.customer_id
WHERE b.balance_date > DATEADD(day, -90, m.d)
  AND (DAYOFWEEK(b.balance_date) = 0 OR b.balance_date = m.d)  -- Sundays + latest day
GROUP BY b.balance_date, segment
ORDER BY segment, b.balance_date;

-- 6) Payment terms vs. actual payment behavior by segment (cleared invoices)
SELECT
    COALESCE(c.customer_segment, '(unknown)')                              AS segment,
    COUNT(DISTINCT a.customer_id)                                          AS customers,
    ROUND(AVG(a.payment_terms_days), 1)                                    AS avg_terms_days,
    ROUND(AVG(IFF(a.is_cleared, a.days_to_pay, NULL)), 1)                  AS avg_days_to_pay,
    ROUND(AVG(IFF(a.is_cleared, a.days_paid_late, NULL)), 1)               AS avg_days_paid_late,
    ROUND(100 * AVG(IFF(a.is_cleared, IFF(a.days_paid_late > 0, 1, 0), NULL)), 1) AS pct_paid_late
FROM "STREAMLIT-CORTEX-20261018".SILVER.FCT_AR_ITEMS a
LEFT JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_CUSTOMER c
    ON c.customer_id = a.customer_id
GROUP BY segment
ORDER BY segment;
