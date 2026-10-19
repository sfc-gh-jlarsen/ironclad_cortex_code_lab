"""Read-only SQL for the Transfer Planner.

Adapted from sql/transfer_planner/transfer_analysis.sql. Every statement is a fixed
SELECT with no user input spliced in; plant / window filters are applied to the cached
results in pandas, so widget changes never trigger a new query. The transfer-vs-buy
recommendation comes straight from GOLD.FCT_TRANSFER_VS_REORDER and is not recomputed.
"""

DB = '"STREAMLIT-CORTEX-20261018"'
GOLD = f"{DB}.GOLD"

# Today's below-ROP raw materials = latest snapshot_date in the gold decision table.
TODAY_ACTIONS = f"""
SELECT
    t.snapshot_date,
    t.plant_id,
    p.plant_name,
    t.material_id,
    m.material_description,
    t.uom,
    t.needed_qty,
    t.donor_plant_id,
    dp.plant_name                AS donor_plant_name,
    t.transferable_qty,
    t.transport_mode,
    t.transfer_lead_time_days,
    t.transfer_cost_usd,
    t.primary_supplier_id,
    t.reorder_lead_time_days,
    t.reorder_cost_usd,
    t.working_capital_avoided_usd,
    t.recommended_action
FROM {GOLD}.FCT_TRANSFER_VS_REORDER t
JOIN {GOLD}.DIM_PLANT p     ON p.plant_id = t.plant_id
JOIN {GOLD}.DIM_MATERIAL m  ON m.material_id = t.material_id
LEFT JOIN {GOLD}.DIM_PLANT dp ON dp.plant_id = t.donor_plant_id
WHERE t.snapshot_date = (SELECT MAX(snapshot_date) FROM {GOLD}.FCT_TRANSFER_VS_REORDER)
ORDER BY t.plant_id, t.material_id
"""

# Every other plant with surplus (>1.5x its ROP) on the latest day for today's shortages.
# Raw facts only (surplus, lane transit/freight rates); no re-ranking of donors.
# Lanes live in BRONZE.STG_WMS__LANES (no GOLD equivalent yet).
OTHER_DONORS = f"""
WITH today AS (
    SELECT snapshot_date, plant_id, material_id, donor_plant_id
    FROM {GOLD}.FCT_TRANSFER_VS_REORDER
    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM {GOLD}.FCT_TRANSFER_VS_REORDER)
)
SELECT
    t.plant_id,
    t.material_id,
    d.plant_id                         AS candidate_plant_id,
    p.plant_name                       AS candidate_plant_name,
    d.surplus_above_1_5x_rop_qty       AS surplus_qty,
    l.transport_mode,
    l.transit_days,
    l.cost_per_kg_usd,
    l.handling_fee_usd,
    d.plant_id = t.donor_plant_id      AS is_best_donor
FROM today t
JOIN {GOLD}.FCT_INVENTORY_POSITION_DAILY d
  ON d.snapshot_date = t.snapshot_date AND d.material_id = t.material_id
 AND d.plant_id <> t.plant_id AND d.surplus_above_1_5x_rop_qty > 0
JOIN {GOLD}.DIM_PLANT p ON p.plant_id = d.plant_id
LEFT JOIN {DB}.BRONZE.STG_WMS__LANES l
  ON l.from_plant_id = d.plant_id AND l.to_plant_id = t.plant_id
ORDER BY t.plant_id, t.material_id, is_best_donor DESC, l.transit_days
"""

# Full history of the decision table (small: ~500 rows) for shortage counts and missed transfers.
HISTORY = f"""
SELECT
    t.snapshot_date,
    t.plant_id,
    p.plant_name,
    t.material_id,
    t.recommended_action,
    t.actual_action,
    t.working_capital_avoided_usd
FROM {GOLD}.FCT_TRANSFER_VS_REORDER t
JOIN {GOLD}.DIM_PLANT p ON p.plant_id = t.plant_id
"""
