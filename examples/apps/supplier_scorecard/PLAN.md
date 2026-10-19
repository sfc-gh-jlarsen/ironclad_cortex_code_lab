# Supplier Scorecard – Plan

Read-only Streamlit app for procurement's monthly business review. It replaces the Tableau supplier
scorecard. All data comes from `"STREAMLIT-CORTEX-20261018".GOLD`.

There was no Tableau screenshot. The layout follows the described markup: keep the on-time delivery
(OTD) chart, drop the pie chart, add quality rejects and risk score.

## Sources
- `FCT_SUPPLIER_SCORECARD_MONTHLY`: month × supplier × plant line counts, spend, quantities, monthly avg risk score.
- `DIM_SUPPLIER`: name, `PRIMARY_CATEGORY` (defines peers), latest risk sub-scores, tier, alert count.
- `DIM_PLANT`: plant names.
- `FCT_PO_PRICE_VARIANCE` + `DIM_MATERIAL`: single-source materials (exactly one supplier in PO history).
  This returns the same 4 materials as the BRONZE info-record check.
- Queries #5 and #7 of `sql/supplier_scorecard/supplier_otd_analysis.sql` are not used because they read BRONZE.
  Weekly risk history is replaced by the monthly averages, so there is no weekly alert detail.

## Files
- `streamlit_app.py`: UI (picker, watchlist, KPIs, trends, plant exposure, risk, single-source)
- `queries.py`: three fixed GOLD SELECTs
- `reconciliation.sql`: tie-out to the exploration numbers (PASS/FAIL)
- `snowflake.yml`, `pyproject.toml`, `.streamlit/config.toml`

## Metrics (recomputed from summed counts after filtering, never averaged)
- OTD % = on_time_lines / (received_lines + overdue_open_lines). Overdue PO lines that haven't been received count as late.
- OTIF % = otif_lines / the same denominator
- Reject % = rejected_qty / received_qty
- Avg delay = SUM(avg_receipt_delay_days × received_lines) / SUM(received_lines)
- Peers = all other suppliers with the same `PRIMARY_CATEGORY`, pooled.

## Making the declining supplier obvious
- Watchlist: OTD in the latest 2 months vs. all earlier months for every supplier.
  - Ranked by extra late lines = OTD drop × recent line count.
  - Suppliers with fewer than 20 lines in either period show as "Low volume" and aren't ranked. This keeps the
    partial current month and tiny suppliers from crowding the top.
  - Status: Declining ≤ −15 pts, Watch ≤ −5 pts, otherwise Stable.
- The supplier picker defaults to the top of the watchlist. Today that is Meridian Carbon Solutions
  (−17.5 pts, ~26 extra late lines).
- The current month is labelled MTD and drawn faded on the trend charts.

## Filters
- Supplier: single select, defaults to the top of the watchlist.
- Plant: multiselect (empty = all). Applies to the KPIs and trend charts. Plant exposure always shows every plant.

## Guardrails
- `st.connection("snowflake")` only, with no credentials in code
- SELECT statements only, with no DDL or DML. No user input is ever inserted into SQL.
- Three cached loads (1h TTL); a Refresh button clears the cache.
- Recommended: run the app under a role that can only read GOLD, not ACCOUNTADMIN.
