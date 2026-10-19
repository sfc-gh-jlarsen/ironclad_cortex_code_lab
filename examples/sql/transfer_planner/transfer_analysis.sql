-- Transfer instead of buy: are plants purchasing raw materials a sister plant could have sent?
-- Source: "STREAMLIT-CORTEX-20261018".GOLD (plus BRONZE for lanes / purchasing info records)
--
-- Findings (history 2026-07-21 to 2026-10-18, 90 days):
--   * Data: daily inventory by plant x material with ROP, safety stock and surplus
--     (GOLD.FCT_INVENTORY_POSITION_DAILY, 16,920 rows); 30 plant-to-plant lanes with transit days,
--     $/kg freight and handling fee (BRONZE.STG_WMS__LANES); primary-supplier contract price and
--     lead time (BRONZE.STG_SAP__PURCHASING_INFO_RECORDS); a precomputed decision table
--     (GOLD.FCT_TRANSFER_VS_REORDER, 471 rows, one per below-ROP raw-material day).
--   * Carbon black: Valle Alto (P400) / N234 tread grade is the most frequent shortage of any
--     plant/material (56 of 90 days below ROP), and another plant had surplus on those days.
--     Every other carbon black combination was 1-2 days.
--   * Best donor for P400 N234 is usually Cedar Bluff P200 (31 days, 6-day truck, including today 2026-10-18),
--     then Pine Hollow P600 (16, 7-day truck), Ridgeport P100 (9, last on 2026-09-02).
--   * Recommended TRANSFER but actually placed a PO on 147 days. That is $5.32M of purchase spend
--     that could have been sourced from a sister plant, against $0.29M freight, so ~$5.03M net avoidable.
--     Top: Hollis resin $2.11M, Ridgeport bead wire $0.88M, Cedar Bluff NR RSS3 $0.72M, Valle Alto carbon black N234 $0.50M.
--
-- How the recommendation is calculated (GOLD.FCT_TRANSFER_VS_REORDER):
--   need       = reorder_point + safety_stock - unrestricted_qty   (raw materials, ROH, below ROP only)
--   donor      = any other plant on the same day with surplus above 1.5x its own ROP, connected by a lane.
--                Pick the donor that covers >= 50% of the need first, then shortest transit, then cheapest.
--   transfer $ = transferable_qty * net_weight_kg * lane cost_per_kg + lane handling fee
--   reorder $  = need * primary-supplier contract price
--   TRANSFER if: donor covers >= 50% of need AND transit days < supplier lead time
--                AND freight < 25% of the purchase value of the transferred qty. Otherwise REORDER.
--   net avoidable (working_capital_avoided_usd) = transferable_qty * contract price - transfer $
--   actual_action = TRANSFER / PO / NONE, taken from stock transfers and POs created that day.
-- "Avoidable" counts only days where we recommended TRANSFER and a PO was actually placed, so a
-- multi-day shortage is counted on PO days only, not on every day it was below ROP.

-- 1) What data do we have? Plants, lanes, carbon black materials, coverage
SELECT plant_id, plant_name, city, country_code
FROM "STREAMLIT-CORTEX-20261018".GOLD.DIM_PLANT ORDER BY plant_id;

SELECT from_plant_id, to_plant_id, transport_mode, distance_km, transit_days,
       cost_per_kg_usd, handling_fee_usd
FROM "STREAMLIT-CORTEX-20261018".BRONZE.STG_WMS__LANES
ORDER BY from_plant_id, to_plant_id;

SELECT material_id, material_description, material_category, net_weight_kg, is_critical_material
FROM "STREAMLIT-CORTEX-20261018".GOLD.DIM_MATERIAL
WHERE material_category = 'Carbon Black';

SELECT MIN(snapshot_date) AS first_day, MAX(snapshot_date) AS last_day, COUNT(*) AS rows_
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_INVENTORY_POSITION_DAILY;

-- 2) Carbon black: days below ROP in the last 90 days, and whether another plant had surplus that day
WITH inv AS (
    SELECT *
    FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_INVENTORY_POSITION_DAILY
    WHERE snapshot_date > (SELECT MAX(snapshot_date)
                           FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_INVENTORY_POSITION_DAILY) - 90
)
SELECT s.plant_id, s.material_id,
       COUNT(DISTINCT s.snapshot_date)                                        AS days_below_rop,
       COUNT(DISTINCT IFF(s.is_below_safety_stock, s.snapshot_date, NULL))    AS days_below_ss,
       COUNT(DISTINCT IFF(d.plant_id IS NOT NULL, s.snapshot_date, NULL))     AS days_with_surplus_elsewhere,
       LISTAGG(DISTINCT d.plant_id, ',')                                      AS surplus_plants
FROM inv s
LEFT JOIN inv d
    ON d.snapshot_date = s.snapshot_date AND d.material_id = s.material_id
   AND d.plant_id <> s.plant_id AND d.surplus_above_1_5x_rop_qty > 0
WHERE s.is_below_reorder_point AND s.material_id LIKE 'RM-CB-%'
GROUP BY s.plant_id, s.material_id
ORDER BY days_below_rop DESC;

-- 3) All raw materials: most frequent below-ROP combos, donor availability, recommended vs actual
SELECT plant_id, material_id,
       COUNT(*)                                        AS days_below_rop,
       COUNT(donor_plant_id)                           AS days_with_donor,
       MODE(donor_plant_id)                            AS usual_donor,
       SUM(IFF(recommended_action = 'TRANSFER', 1, 0)) AS days_rec_transfer,
       SUM(IFF(actual_action = 'PO', 1, 0))            AS days_po,
       SUM(IFF(actual_action = 'TRANSFER', 1, 0))      AS days_transfer
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER
WHERE snapshot_date > (SELECT MAX(snapshot_date)
                       FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER) - 90
GROUP BY plant_id, material_id
ORDER BY days_below_rop DESC
LIMIT 15;

-- 4) Valle Alto carbon black N234: which donor, lane and economics
SELECT donor_plant_id, transport_mode, transfer_lead_time_days, reorder_lead_time_days,
       COUNT(*)                         AS days,
       ROUND(AVG(needed_qty))           AS avg_need,
       ROUND(AVG(transferable_qty))     AS avg_transferable,
       ROUND(AVG(transfer_cost_usd))    AS avg_freight_usd,
       ROUND(AVG(reorder_cost_usd))     AS avg_po_cost_usd,
       MAX(snapshot_date)               AS last_day
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER
WHERE plant_id = 'P400' AND material_id = 'RM-CB-N234'
GROUP BY ALL
ORDER BY days DESC;

-- 5) Avoidable purchase spend: recommended TRANSFER but bought instead, by plant and material
--    (top row with NULL keys is the grand total)
SELECT t.plant_id, p.plant_name, t.material_id, m.material_description,
       COUNT(*)                                                                    AS missed_transfer_days,
       ROUND(SUM(t.transferable_qty * DIV0NULL(t.reorder_cost_usd, t.needed_qty))) AS purchase_spend_displaceable_usd,
       ROUND(SUM(t.transfer_cost_usd))                                             AS freight_usd,
       ROUND(SUM(t.working_capital_avoided_usd))                                   AS net_avoidable_usd
FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER t
JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_PLANT p    ON p.plant_id = t.plant_id
JOIN "STREAMLIT-CORTEX-20261018".GOLD.DIM_MATERIAL m ON m.material_id = t.material_id
WHERE t.recommended_action = 'TRANSFER' AND t.actual_action = 'PO'
GROUP BY ROLLUP ((t.plant_id, p.plant_name, t.material_id, m.material_description))
ORDER BY net_avoidable_usd DESC NULLS FIRST;
