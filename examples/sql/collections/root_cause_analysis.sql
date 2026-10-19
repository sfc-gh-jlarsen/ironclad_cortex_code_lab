-- =====================================================================
-- Vignette 4 Explore: "Add the why" - fulfillment root cause of disputes
-- Source: "STREAMLIT-CORTEX-20261018".GOLD (read-only)
--
-- Key table: GOLD.FCT_ORDER_FULFILLMENT (grain = sales order line)
--   IS_ON_TIME / IS_IN_FULL / IS_OTIF, DELIVERY_DELAY_DAYS, FILL_RATE
--   HAS_DISPUTE, DISPUTE_REASON, MAX_DAYS_PAID_LATE, OPEN_AR_USD
-- Also: GOLD.FCT_AR_OPEN_ITEMS_AGING carries WAS_DELIVERED_LATE /
--   WAS_SHORT_SHIPPED per open invoice (what the Collections app shows).
--
-- Caveats
--   * Open / Past Due lines have IS_ON_TIME = NULL but IS_OTIF = FALSE.
--     They are excluded below (shipped lines only) so they don't
--     deflate the non-disputed OTIF rate (73.0% raw vs 82.2% shipped).
--   * MAX_DAYS_PAID_LATE is NULL for unpaid lines; averages are over
--     paid lines only.
--   * SHORT_SHIPMENT disputes are 90% late but only 29% IS_IN_FULL=FALSE:
--     the generator's reason codes don't fully match the line flags.
-- =====================================================================

-- 1. Dispute rate by fulfillment cause
--    Result (2026-10-19): Late+short 32.5% | Late only 19.1% |
--    Short only 14.3% (n=14) | OTIF 3.6%  -> late ~5x, late+short ~9x OTIF
SELECT
    CASE WHEN NOT is_on_time AND NOT is_in_full THEN 'Late + short'
         WHEN NOT is_on_time                    THEN 'Late only'
         WHEN NOT is_in_full                    THEN 'Short only'
         ELSE 'OTIF' END                                  AS cause,
    COUNT(*)                                              AS lines,
    COUNT_IF(has_dispute)                                 AS disputed_lines,
    ROUND(100 * COUNT_IF(has_dispute) / COUNT(*), 2)      AS dispute_rate_pct,
    ROUND(AVG(max_days_paid_late), 1)                     AS avg_max_days_paid_late,
    ROUND(SUM(net_value_usd))                             AS net_value_usd
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_ORDER_FULFILLMENT
WHERE is_on_time IS NOT NULL            -- shipped lines only
GROUP BY 1
ORDER BY dispute_rate_pct DESC;

-- 2. OTIF rate: disputed vs non-disputed (shipped lines)
--    Result: Disputed 40.5% OTIF (n=435) vs Not disputed 82.2% (n=5,708)
--    Disputed lines also pay later: ~9 vs ~2 avg max days paid late
SELECT
    IFF(has_dispute, 'Disputed', 'Not disputed')          AS dispute_group,
    COUNT(*)                                              AS lines,
    ROUND(100 * COUNT_IF(is_otif)     / COUNT(*), 1)      AS otif_pct,
    ROUND(100 * COUNT_IF(is_on_time)  / COUNT(*), 1)      AS on_time_pct,
    ROUND(100 * COUNT_IF(is_in_full)  / COUNT(*), 1)      AS in_full_pct,
    ROUND(AVG(delivery_delay_days), 1)                    AS avg_delay_days,
    ROUND(AVG(fill_rate), 3)                              AS avg_fill_rate,
    ROUND(AVG(max_days_paid_late), 1)                     AS avg_max_days_paid_late
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_ORDER_FULFILLMENT
WHERE is_on_time IS NOT NULL
GROUP BY 1
ORDER BY 1;

-- 3. Top dispute reasons, with fulfillment + payment profile
--    Result: SHORT_SHIPMENT 32.4% | LATE_DELIVERY 30.3% |
--    PRICING_DISCREPANCY 15.2% | DUPLICATE_BILLING 13.6% | DAMAGED_GOODS 8.5%
--    ~63% of disputes are fulfillment-driven; the rest are billing/quality
--    issues on OTIF lines, and those pay the latest (10-18 days).
SELECT
    dispute_reason,
    COUNT(*)                                              AS disputed_lines,
    COUNT(DISTINCT sales_order_id)                        AS orders,
    ROUND(100 * RATIO_TO_REPORT(COUNT(*)) OVER (), 1)     AS pct_of_disputed,
    ROUND(100 * COUNT_IF(is_otif) / COUNT(*), 1)          AS otif_pct,
    ROUND(100 * COUNT_IF(NOT is_on_time) / COUNT(*), 1)   AS late_pct,
    ROUND(100 * COUNT_IF(NOT is_in_full) / COUNT(*), 1)   AS short_pct,
    ROUND(AVG(max_days_paid_late), 1)                     AS avg_max_days_paid_late,
    ROUND(SUM(net_value_usd))                             AS net_value_usd
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_ORDER_FULFILLMENT
WHERE has_dispute
GROUP BY 1
ORDER BY disputed_lines DESC;

-- 4. Customer drill-down for the planned Root Cause tab
SELECT
    f.customer_id, c.customer_name, f.sales_order_id, f.sales_order_line_id,
    f.order_date, f.requested_delivery_date, f.first_goods_issue_date,
    f.delivery_delay_days, f.fill_rate, f.is_on_time, f.is_in_full, f.is_otif,
    f.has_dispute, f.dispute_reason, f.max_days_paid_late, f.open_ar_usd
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_ORDER_FULFILLMENT f
LEFT JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_CUSTOMER c ON c.customer_id = f.customer_id
WHERE f.is_on_time IS NOT NULL
  AND (NOT f.is_otif OR f.has_dispute)
ORDER BY f.customer_id, f.delivery_delay_days DESC;
