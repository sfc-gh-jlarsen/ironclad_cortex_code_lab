-- Carbon black supplier on-time delivery check
-- Source: "STREAMLIT-CORTEX-20261018".GOLD (plus BRONZE for info records / raw risk feed)
--
-- Findings (history 2026-07 to 2026-10; October is a partial month):
--   * The supplier is Meridian Carbon Solutions (0000100006). OTD fell 70.4% -> 65.5% -> 52.8% -> 43.6%,
--     while the other carbon black suppliers held at 71-87%.
--   * Reject rate rose 1.7% -> 5.1% (Sep), against ~1-2% for peers. Avg delay peaked at 3.0 days in Sep.
--   * Valle Alto (P400) is most exposed: 81% of its carbon black spend goes to Meridian.
--   * Single-source materials: steel cord RM-SC-001 / RM-SC-002 (critical, Kestrel), silica RM-SIL-001, resin RM-RES-001.
--   * Risk scores come from a weekly third-party JSON feed (RAW.SUP_RISK_SCORES, SOURCE_SYSTEM = RISK_INTEL_VENDOR).
--     Higher score = healthier. Meridian's delivery sub-score fell 84 -> 49, with HIGH delivery alerts since mid-Sep.

-- On-time rate definition (from the GOLD.FCT_SUPPLIER_SCORECARD_MONTHLY build):
--   on_time_rate = on_time_lines / (received_lines + overdue_open_lines)
--   Overdue-but-unreceived lines count as late, so recent months don't look better than they are.
--   Re-aggregate from the line counts; do not average the ON_TIME_RATE column.

-- 1) Carbon black suppliers, with latest risk score
SELECT supplier_id, supplier_name, country_code, materials_supplied,
       overall_risk_score, delivery_score, risk_tier, risk_score_date
FROM "STREAMLIT-CORTEX-20261018".GOLD.DIM_SUPPLIER
WHERE primary_category = 'Carbon Black'
ORDER BY supplier_id;

-- 2) Monthly on-time rate and avg delay, per carbon black supplier (which one is declining?)
SELECT
    s.supplier_name,
    f.month_start_date,
    SUM(f.po_lines)                                                        AS po_lines,
    ROUND(100 * DIV0NULL(SUM(f.on_time_lines),
                         SUM(f.received_lines) + SUM(f.overdue_open_lines)), 1) AS otd_pct,
    ROUND(DIV0NULL(SUM(f.avg_receipt_delay_days * f.received_lines),
                   SUM(f.received_lines)), 2)                              AS avg_delay_days
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_SUPPLIER_SCORECARD_MONTHLY f
JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_SUPPLIER s
    ON s.supplier_id = f.supplier_id
WHERE s.primary_category = 'Carbon Black'
GROUP BY s.supplier_name, f.month_start_date
ORDER BY s.supplier_name, f.month_start_date;

-- 3) Meridian vs. the other carbon black suppliers: monthly OTD, OTIF, reject rate, avg delay
SELECT
    f.month_start_date,
    IFF(f.supplier_id = '0000100006', 'Meridian Carbon Solutions', 'Other carbon black') AS supplier_group,
    SUM(f.po_lines)                                                        AS po_lines,
    SUM(f.received_lines)                                                  AS received_lines,
    SUM(f.overdue_open_lines)                                              AS overdue_open_lines,
    ROUND(100 * DIV0NULL(SUM(f.on_time_lines),
                         SUM(f.received_lines) + SUM(f.overdue_open_lines)), 1) AS otd_pct,
    ROUND(100 * DIV0NULL(SUM(f.otif_lines),
                         SUM(f.received_lines) + SUM(f.overdue_open_lines)), 1) AS otif_pct,
    ROUND(100 * DIV0NULL(SUM(f.rejected_qty), SUM(f.received_qty)), 2)     AS reject_pct,
    ROUND(DIV0NULL(SUM(f.avg_receipt_delay_days * f.received_lines),
                   SUM(f.received_lines)), 2)                              AS avg_delay_days
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_SUPPLIER_SCORECARD_MONTHLY f
JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_SUPPLIER s
    ON s.supplier_id = f.supplier_id
WHERE s.primary_category = 'Carbon Black'
GROUP BY f.month_start_date, supplier_group
ORDER BY supplier_group, f.month_start_date;

-- 4) Plant exposure to Meridian: share of each plant's carbon black spend, and Meridian's OTD there
WITH cb AS (
    SELECT
        f.plant_id,
        SUM(f.spend_usd)                                                   AS cb_spend_usd,
        SUM(IFF(f.supplier_id = '0000100006', f.spend_usd, 0))             AS meridian_spend_usd,
        SUM(IFF(f.supplier_id = '0000100006', f.po_lines, 0))              AS meridian_po_lines,
        SUM(IFF(f.supplier_id = '0000100006', f.overdue_open_lines, 0))    AS meridian_overdue_open,
        SUM(IFF(f.supplier_id = '0000100006', f.on_time_lines, 0))         AS meridian_on_time,
        SUM(IFF(f.supplier_id = '0000100006', f.received_lines + f.overdue_open_lines, 0)) AS meridian_otd_base
    FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_SUPPLIER_SCORECARD_MONTHLY f
    JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_SUPPLIER s
        ON s.supplier_id = f.supplier_id
    WHERE s.primary_category = 'Carbon Black'
    GROUP BY f.plant_id
)
SELECT
    cb.plant_id,
    p.plant_name,
    p.region,
    ROUND(cb.meridian_spend_usd)                                           AS meridian_spend_usd,
    ROUND(100 * DIV0NULL(cb.meridian_spend_usd, cb.cb_spend_usd), 1)       AS pct_cb_spend_meridian,
    cb.meridian_po_lines,
    cb.meridian_overdue_open,
    ROUND(100 * DIV0NULL(cb.meridian_on_time, cb.meridian_otd_base), 1)    AS meridian_otd_pct
FROM cb
JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_PLANT p
    ON p.plant_id = cb.plant_id
WHERE cb.meridian_po_lines > 0
ORDER BY pct_cb_spend_meridian DESC, meridian_spend_usd DESC;

-- 5) Single-source materials (only one supplier with a currently valid purchasing info record)
-- Note: info records are not exposed in GOLD; this reads BRONZE. Consider a GOLD model before the app uses it.
SELECT
    m.material_id,
    m.material_description,
    m.material_category,
    m.is_critical_material,
    COUNT(DISTINCT i.supplier_id)                                          AS supplier_count,
    ANY_VALUE(s.supplier_name)                                             AS only_supplier
FROM "STREAMLIT-CORTEX-20261018".BRONZE.STG_SAP__PURCHASING_INFO_RECORDS i
JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_MATERIAL m
    ON m.material_id = i.material_id
JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_SUPPLIER s
    ON s.supplier_id = i.supplier_id
WHERE CURRENT_DATE BETWEEN i.valid_from AND COALESCE(i.valid_to, '9999-12-31')
GROUP BY m.material_id, m.material_description, m.material_category, m.is_critical_material
HAVING supplier_count = 1
ORDER BY m.material_category, m.material_id;

-- Risk score lineage:
--   RAW.SUP_RISK_SCORES        weekly (Mondays) JSON payload from a third-party risk vendor (SOURCE_SYSTEM = RISK_INTEL_VENDOR)
--   BRONZE.STG_RISK__SUPPLIER_RISK_SCORES  parses JSON: financial / geopolitical / esg / delivery sub-scores,
--                                          overall_score, alerts array; dedupes on FEED_ID (latest INGESTED_AT)
--   GOLD.DIM_SUPPLIER          latest score per supplier; RISK_TIER = High (<70) / Medium (<80) / Low (>=80)
--   GOLD.FCT_SUPPLIER_SCORECARD_MONTHLY    monthly avg overall + delivery score (AVG_RISK_SCORE, AVG_DELIVERY_RISK_SCORE)
--   Scale: higher = healthier / lower risk.

-- 6) Risk feed profile: coverage, cadence, range, freshness
SELECT
    COUNT(*)                          AS score_rows,
    COUNT(DISTINCT supplier_id)       AS suppliers,
    MIN(score_date)                   AS first_score_date,
    MAX(score_date)                   AS last_score_date,
    COUNT(DISTINCT score_date)        AS weekly_snapshots,
    MIN(overall_risk_score)           AS min_overall,
    ROUND(AVG(overall_risk_score), 1) AS avg_overall,
    MAX(overall_risk_score)           AS max_overall,
    SUM(alert_count)                  AS total_alerts,
    MAX(ingested_at)                  AS last_ingested_at
FROM "STREAMLIT-CORTEX-20261018".BRONZE.STG_RISK__SUPPLIER_RISK_SCORES;

-- 7) Weekly risk scores and alerts for the carbon black suppliers
SELECT
    s.supplier_name,
    r.score_date,
    r.overall_risk_score,
    r.delivery_score,
    r.financial_score,
    r.geopolitical_score,
    r.esg_score,
    r.alert_count,
    r.alerts
FROM "STREAMLIT-CORTEX-20261018".BRONZE.STG_RISK__SUPPLIER_RISK_SCORES r
JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_SUPPLIER s
    ON s.supplier_id = r.supplier_id
WHERE s.primary_category = 'Carbon Black'
ORDER BY s.supplier_name, r.score_date;
