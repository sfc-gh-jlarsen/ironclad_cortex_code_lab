-- Reconciliation: Transfer Planner app KPIs vs "STREAMLIT-CORTEX-20261018".GOLD
-- Run in a worksheet; each number should match the app with no plant filter and a 90-day window.

-- 1) Today's list: row count, transfer count, avoidable $ (KPIs 1-3 and the Today's actions table)
SELECT snapshot_date,
       COUNT(*)                                                         AS shortages_today,
       COUNT_IF(recommended_action = 'TRANSFER')                        AS recommended_transfers,
       ROUND(SUM(IFF(recommended_action = 'TRANSFER', working_capital_avoided_usd, 0))) AS avoidable_today_usd,
       ROUND(SUM(reorder_cost_usd))                                     AS purchase_usd,
       ROUND(SUM(transfer_cost_usd))                                    AS freight_usd
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER)
GROUP BY snapshot_date;

-- 2) Missed transfers in the last 90 days (KPI 4 and the end point of the cumulative chart)
SELECT COUNT(*) AS missed_days, ROUND(SUM(working_capital_avoided_usd)) AS missed_usd
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER
WHERE recommended_action = 'TRANSFER' AND actual_action = 'PO'
  AND snapshot_date > (SELECT MAX(snapshot_date) FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER) - 90;

-- 3) Shortage days by plant, last 90 days (bar chart)
SELECT p.plant_name, COUNT(*) AS shortage_days
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER t
JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_PLANT p ON p.plant_id = t.plant_id
WHERE t.snapshot_date > (SELECT MAX(snapshot_date) FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER) - 90
GROUP BY p.plant_name
ORDER BY shortage_days DESC;

-- 4) Valle Alto (P400) carbon black today: best donor and every candidate (Cedar Bluff P200 should be best)
SELECT d.plant_id AS candidate, ROUND(d.surplus_above_1_5x_rop_qty) AS surplus_qty, l.transit_days,
       d.plant_id = t.donor_plant_id AS is_best_donor, t.recommended_action
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER t
JOIN "STREAMLIT-CORTEX-20261018".GOLD.FCT_INVENTORY_POSITION_DAILY d
  ON d.snapshot_date = t.snapshot_date AND d.material_id = t.material_id
 AND d.plant_id <> t.plant_id AND d.surplus_above_1_5x_rop_qty > 0
LEFT JOIN "STREAMLIT-CORTEX-20261018".BRONZE.STG_WMS__LANES l
  ON l.from_plant_id = d.plant_id AND l.to_plant_id = t.plant_id
WHERE t.plant_id = 'P400' AND t.material_id = 'RM-CB-N234'
  AND t.snapshot_date = (SELECT MAX(snapshot_date) FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER)
ORDER BY is_best_donor DESC, l.transit_days;
