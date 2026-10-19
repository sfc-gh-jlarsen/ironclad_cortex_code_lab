# Collections Cockpit – Plan

Read-only Streamlit app for the AR team. All data comes from `"STREAMLIT-CORTEX-20261018".GOLD`.

## Sources
- `FCT_AR_OPEN_ITEMS_AGING`: invoice-level open items, a single snapshot (AS_OF_DATE 2026-10-18).
- `FCT_AR_DAILY_BALANCE`: daily balances, 2026-07-23 to 2026-10-18. Used for DSO.
- `DIM_CUSTOMER`: customer name and segment.
- Query #6 of `ar_aging_analysis.sql` is excluded because it reads SILVER.

## Files
- `streamlit_app.py`: UI (filters, KPIs, charts, top customers and invoice drill-down)
- `queries.py`: fixed GOLD SELECTs
- `reconciliation.sql`: KPI tie-out
- `snowflake.yml`, `pyproject.toml`, `.streamlit/config.toml`

## Filters
- Company code and Segment: multiselects, empty = all. They apply to every tile.
- As of: sets the DSO KPI date and the end of the 90-day DSO trend. The open-item tiles always use the aging snapshot.

## KPIs
- Open AR $ = SUM(open_amount_usd)
- Past due $ = the same sum WHERE days_past_due > 0
- DSO = SUM(ar_balance_usd) / (SUM(sales_trailing_90d_usd) / 90), calculated on totals, not as an average of CUSTOMER_DSO_DAYS
- In dispute $ = SUM(open_amount_usd) WHERE is_in_active_dispute

## Guardrails
- `st.connection("snowflake")` only, with no credentials in code
- SELECT statements only, with no DDL or DML. No user input is ever inserted into SQL.
- Caching: three cached loads (1h TTL). Filters and row clicks work on the cached data, and a Refresh button clears the cache.
- Recommended: run the app under a role that can only read GOLD, not ACCOUNTADMIN.
