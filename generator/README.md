# Data generator: Ironclad Tire & Rubber Co.

This generator creates a realistic, **entirely fictional** SAP-style dataset for a tire manufacturer. It writes the
`RAW` schema of `"STREAMLIT-CORTEX-20261018"`, and the dbt project in `../dbt_ironclad/` builds BRONZE → SILVER → GOLD on top of it.

All names in the data are made up. That includes the company, plants, suppliers, customers, people and inspector codes.
Plant coordinates are approximate regional placeholders, not real facilities.

> You don't have to run this. The same data ships as Parquet in `../data/raw/` (about 1.5 MB, 29 tables, about 72K rows)
> and loads in a minute with `../setup/load_raw.sql`. Run the generator when you want dates that end **yesterday**
> instead of the date the Parquet snapshot was taken.

## What it generates

| Area | RAW tables | Notes |
|---|---|---|
| Master data | `T001` company codes, `T001W` plants, `MARA`/`MARC` materials, `LFA1` suppliers, `EINA` info records, `KNA1` customers, `WMS_TRANSFER_LANES` | 3 company codes (US/MX/DE, USD/MXN/EUR), 6 plants, 41 materials, 20 suppliers, 144 customers (OEM / dealer / fleet) |
| Procure-to-pay | `EKKO`/`EKPO` POs, `EKBE` goods receipts, `RBKP`/`RSEG` supplier invoices | 3-way-match ready; some invoices are over-billed on purpose |
| Order-to-cash | `VBAK`/`VBAP` orders, `LIKP`/`LIPS` deliveries, `VBRK`/`VBRP` billing, `BSID_BSAD` AR, `PAYMENTS`, `AR_DISPUTES` (event log) | Late or short deliveries drive disputes, and disputes delay payment |
| Inventory and logistics | `MARD` daily stock snapshot, `WMS_STOCK_TRANSFERS`, `WMS_TRANSFER_RECEIPTS` | Daily, by plant × material |
| Semi-structured feeds | `SUP_QUALITY_INSPECTIONS` (JSON per goods receipt), `SUP_RISK_SCORES` (weekly JSON) | Used for the "flatten the JSON" demo |
| Reference | `FX_RATES` | Daily USD→MXN/EUR |
| Bookkeeping | `GEN_LOAD_LOG` | One row per generated day (drives gap-filling) |

### Built-in storylines (what the demo prompts "discover")

1. **Collections / DSO:** a handful of slow payers (e.g. *Valtor Trucks*) plus dispute-driven late payments.
2. **Declining supplier:** *Meridian Carbon Solutions* (`0000100006`), the primary carbon black N234 source. Its on-time
   rate falls and its reject rate rises, starting `DECLINE_LEAD_DAYS` (110) days before the end of the first load.
   Valle Alto (P400) is the most exposed plant.
3. **Transfer instead of buy:** N234 at Valle Alto (P400) repeatedly runs below its reorder point while sister plants
   (Cedar Bluff P200, Pine Hollow P600, Ridgeport P100) carry surplus. Only about 30% of transfer opportunities are
   executed; the rest become POs, which is the "money left on the table."
4. **Root cause:** late or short shipments have much higher dispute rates.

Everything is deterministic. Each document's RNG is seeded from its number, so re-running a day produces identical rows.
The one intentional change is customer credit limits, which move by ISO week so the dbt snapshot captures real SCD2 history.

## Running it

**Prerequisites:** Python 3.10+, `pandas`, `numpy`, and either an active Snowpark session (Snowsight Workspace) or
`snowflake-connector-python[pandas]`. The database and the `RAW` schema must already exist. Run step 1 of
`../setup/load_raw.sql`, or:

```sql
CREATE DATABASE IF NOT EXISTS "STREAMLIT-CORTEX-20261018";
CREATE SCHEMA  IF NOT EXISTS "STREAMLIT-CORTEX-20261018".RAW;
```

**In a Snowsight Workspace:** open `generator/generate.py` and run it. It uses the active session and your current
role/warehouse.

**From a terminal:**

```bash
python generator/generate.py                 # fill the last 90 days (default)
python generator/generate.py --window-days 120
python generator/generate.py --validate-only # only run the integrity checks
```

Outside a Workspace, `Conn` reads an OAuth token file plus these environment variables:
- `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_HOST`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_TOKEN_FILE_PATH`

No credentials are stored in the code. If you use a different auth method (key pair, SSO), swap the `connect(...)` call
in `Conn.__init__`.

Then build the models:

```bash
cd dbt_ironclad && dbt build
```

## How gap-filling works

- Each run targets `[today − window, yesterday]` and skips any day already in `RAW.GEN_LOAD_LOG`.
- Each document's whole lifecycle is simulated on the day it is created. A run inserts only the rows whose
  creation day and event day are both loaded after this run, and were not both loaded before it.
  - So a PO created on day *N* gets its goods receipt inserted by whichever run fills day *N+7*.
  - Child rows always have parents, and the run ends with 19 integrity checks (all should report `0`).
- Master tables are fully replaced on every run, which is safe because they are deterministic.
- Because `GEN_LOAD_LOG` ships in the Parquet files, you can load the Parquet files and then run the generator to **top up**
  the days since the snapshot.

## Reset

To start over, recreate the schemas, then rerun the generator (or the Parquet load) and `dbt build`:

```sql
CREATE OR REPLACE SCHEMA "STREAMLIT-CORTEX-20261018".RAW;
CREATE OR REPLACE SCHEMA "STREAMLIT-CORTEX-20261018".BRONZE;
CREATE OR REPLACE SCHEMA "STREAMLIT-CORTEX-20261018".SILVER;   -- also clears the dbt snapshot
CREATE OR REPLACE SCHEMA "STREAMLIT-CORTEX-20261018".GOLD;
```

## Maintainer: refreshing the shipped Parquet

```bash
python generator/generate.py && (cd dbt_ironclad && dbt build) && python setup/export_raw.py
```

`setup/export_raw.py` writes `data/raw/<TABLE>.parquet` through a user-stage `COPY INTO` + `GET`.

## Files

- `master_data.py`: the fictional company (plants, materials, suppliers, customers, lanes) and the deterministic RNG helpers.
- `generate.py`: the daily simulation, the storyline signals, the loader, and the integrity checks.
