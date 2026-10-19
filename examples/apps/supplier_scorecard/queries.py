"""Read-only SQL against "STREAMLIT-CORTEX-20261018".GOLD for the Supplier Scorecard.

Adapted from sql/supplier_scorecard/supplier_otd_analysis.sql. Every statement is a
fixed SELECT with no user input spliced in; supplier / plant filters are applied to
the cached results in pandas, so widget changes never trigger a new query.
Queries #5 and #7 of that file read BRONZE and are replaced here by GOLD equivalents.
"""

GOLD = '"STREAMLIT-CORTEX-20261018".GOLD'

# Month x supplier x plant line counts. Rates are recomputed in the app from these
# counts after filtering (never averaged). The OTD / OTIF denominator is
# received_lines + overdue_open_lines, so overdue-but-unreceived lines count as late.
SCORECARD = f"""
SELECT
    f.month_start_date,
    f.supplier_id,
    s.supplier_name,
    COALESCE(s.primary_category, '(none)') AS category,
    f.plant_id,
    p.plant_name,
    f.po_lines,
    f.spend_usd,
    f.received_lines,
    f.on_time_lines,
    f.otif_lines,
    f.overdue_open_lines,
    f.avg_receipt_delay_days * f.received_lines AS total_delay_days,
    f.received_qty,
    f.rejected_qty,
    f.avg_risk_score,
    f.avg_delivery_risk_score
FROM {GOLD}.FCT_SUPPLIER_SCORECARD_MONTHLY f
JOIN {GOLD}.DIM_SUPPLIER s ON s.supplier_id = f.supplier_id
LEFT JOIN {GOLD}.DIM_PLANT p ON p.plant_id = f.plant_id
"""

# Latest third-party risk score per supplier (higher = healthier; tier High < 70 <= Medium < 80 <= Low).
SUPPLIERS = f"""
SELECT
    supplier_id,
    supplier_name,
    COALESCE(primary_category, '(none)') AS category,
    country_code,
    materials_supplied,
    risk_score_date,
    overall_risk_score,
    financial_score,
    geopolitical_score,
    esg_score,
    delivery_score,
    risk_alert_count,
    risk_tier
FROM {GOLD}.DIM_SUPPLIER
"""

# Materials bought from exactly one supplier, from PO-line history in GOLD.
# Matches the BRONZE info-record check in supplier_otd_analysis.sql (#5).
SINGLE_SOURCE = f"""
SELECT
    v.material_id,
    m.material_description,
    m.material_category,
    m.is_critical_material,
    ANY_VALUE(v.supplier_id)                 AS supplier_id,
    ANY_VALUE(s.supplier_name)               AS supplier_name,
    COUNT(DISTINCT v.plant_id)               AS plants,
    SUM(v.po_value_usd)                      AS po_value_usd
FROM {GOLD}.FCT_PO_PRICE_VARIANCE v
JOIN {GOLD}.DIM_MATERIAL m ON m.material_id = v.material_id
JOIN {GOLD}.DIM_SUPPLIER s ON s.supplier_id = v.supplier_id
GROUP BY v.material_id, m.material_description, m.material_category, m.is_critical_material
HAVING COUNT(DISTINCT v.supplier_id) = 1
ORDER BY m.is_critical_material DESC, m.material_category, v.material_id
"""
