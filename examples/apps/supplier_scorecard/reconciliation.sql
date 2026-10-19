-- Supplier Scorecard reconciliation: app KPIs vs. GOLD and the exploration results
-- Source: "STREAMLIT-CORTEX-20261018".GOLD
-- Each query returns expected vs. actual and a PASS/FAIL column. Expected values are
-- from sql/supplier_scorecard/supplier_otd_analysis.sql, run on 2026-10-19
-- (Oct 2026 is month-to-date, so October figures move as receipts post).

-- 1) Meridian vs. other carbon black: monthly OTD % and reject %
WITH actual AS (
    SELECT
        f.month_start_date,
        IFF(f.supplier_id = '0000100006', 'Meridian', 'Peers') AS grp,
        ROUND(100 * DIV0NULL(SUM(f.on_time_lines),
                             SUM(f.received_lines) + SUM(f.overdue_open_lines)), 1) AS otd_pct,
        ROUND(100 * DIV0NULL(SUM(f.rejected_qty), SUM(f.received_qty)), 2)     AS reject_pct
    FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_SUPPLIER_SCORECARD_MONTHLY f
    JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_SUPPLIER s ON s.supplier_id = f.supplier_id
    WHERE s.primary_category = 'Carbon Black'
    GROUP BY 1, 2
),
expected (month_start_date, grp, otd_pct, reject_pct) AS (
    SELECT * FROM VALUES
        ('2026-07-01'::DATE, 'Meridian', 70.4, 1.71),
        ('2026-08-01'::DATE, 'Meridian', 65.5, 2.95),
        ('2026-09-01'::DATE, 'Meridian', 52.8, 5.06),
        ('2026-10-01'::DATE, 'Meridian', 43.6, 4.19),
        ('2026-07-01'::DATE, 'Peers',    72.0, 1.17),
        ('2026-08-01'::DATE, 'Peers',    87.0, 1.73),
        ('2026-09-01'::DATE, 'Peers',    75.6, 1.33),
        ('2026-10-01'::DATE, 'Peers',    71.4, 0.95)
)
SELECT
    e.grp, e.month_start_date,
    e.otd_pct    AS expected_otd_pct,    a.otd_pct    AS actual_otd_pct,
    e.reject_pct AS expected_reject_pct, a.reject_pct AS actual_reject_pct,
    IFF(a.otd_pct = e.otd_pct AND a.reject_pct = e.reject_pct, 'PASS', 'FAIL') AS result
FROM expected e
LEFT JOIN actual a ON a.month_start_date = e.month_start_date AND a.grp = e.grp
ORDER BY e.grp, e.month_start_date;

-- 2) Overdue-but-unreceived lines are in the OTD denominator.
-- If they were excluded, Meridian Oct OTD would read higher than 43.6%.
SELECT
    ROUND(100 * DIV0NULL(SUM(on_time_lines), SUM(received_lines) + SUM(overdue_open_lines)), 1) AS otd_with_overdue,
    ROUND(100 * DIV0NULL(SUM(on_time_lines), SUM(received_lines)), 1)                          AS otd_received_only,
    SUM(overdue_open_lines)                                                                    AS overdue_open_lines
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_SUPPLIER_SCORECARD_MONTHLY
WHERE supplier_id = '0000100006'
  AND month_start_date = '2026-10-01';

-- 3) Plant exposure: P400 Valle Alto share of carbon black spend going to Meridian
SELECT
    80.9 AS expected_pct,
    ROUND(100 * DIV0NULL(SUM(IFF(f.supplier_id = '0000100006', f.spend_usd, 0)), SUM(f.spend_usd)), 1) AS actual_pct,
    IFF(actual_pct = expected_pct, 'PASS', 'FAIL') AS result
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_SUPPLIER_SCORECARD_MONTHLY f
JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_SUPPLIER s ON s.supplier_id = f.supplier_id
WHERE s.primary_category = 'Carbon Black'
  AND f.plant_id = 'P400';

-- 4) Single-source materials: GOLD PO history gives the same 4 materials as the BRONZE info records
SELECT
    'RM-RES-001,RM-SC-001,RM-SC-002,RM-SIL-001'                      AS expected,
    LISTAGG(material_id, ',') WITHIN GROUP (ORDER BY material_id)    AS actual,
    IFF(actual = expected, 'PASS', 'FAIL')                           AS result
FROM (
    SELECT material_id
    FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_PO_PRICE_VARIANCE
    GROUP BY material_id
    HAVING COUNT(DISTINCT supplier_id) = 1
);

-- 5) Watchlist: Meridian ranks first on extra late lines (latest 2 months vs. earlier, >= 20 lines each period)
WITH p AS (
    SELECT
        supplier_id,
        IFF(month_start_date >= '2026-09-01', 'recent', 'early') AS period,
        SUM(on_time_lines)                       AS on_time,
        SUM(received_lines + overdue_open_lines) AS base
    FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_SUPPLIER_SCORECARD_MONTHLY
    GROUP BY 1, 2
),
w AS (
    SELECT
        supplier_id,
        MAX(IFF(period = 'early',  base, NULL))                     AS base_early,
        MAX(IFF(period = 'recent', base, NULL))                     AS base_recent,
        100 * MAX(IFF(period = 'early',  DIV0NULL(on_time, base), NULL)) AS otd_early,
        100 * MAX(IFF(period = 'recent', DIV0NULL(on_time, base), NULL)) AS otd_recent
    FROM p
    GROUP BY 1
)
SELECT
    s.supplier_name,
    ROUND(otd_recent - otd_early, 1)                       AS otd_change_pts,
    ROUND((otd_early - otd_recent) / 100 * base_recent, 1) AS extra_late_lines
FROM w
JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_SUPPLIER s ON s.supplier_id = w.supplier_id
WHERE base_early >= 20 AND base_recent >= 20
ORDER BY extra_late_lines DESC
LIMIT 3;
