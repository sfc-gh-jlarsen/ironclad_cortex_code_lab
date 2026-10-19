# Ironclad Tire & Rubber Co.: Explore → Plan → Code → Commit with Cortex Code

A hands-on lab and demo kit for **Cortex Code (CoCo)** on Snowflake. Participants work against a realistic,
**entirely fictional** manufacturing dataset (SAP-style ERP, warehouse, supplier-portal and risk feeds). Using natural
language, they find data, plan a Streamlit app, build it, and ship it.

## 1. Intent

The goal is to show *how to work with an AI coding agent*, not only what it can generate. Each vignette follows the same loop:

| Step | What the participant does | What it shows |
|---|---|---|
| **Explore** | Describe a business problem without naming tables | CoCo discovers data via the catalog, reads lineage, and writes and saves exploratory SQL |
| **Plan** | Give a structured brief: **Target · Material · Guardrails · Success** | Plan mode: the agent proposes, and the human approves before any code is written |
| **Code** | Approve the plan | CoCo builds a Streamlit app plus a reconciliation query |
| **Commit** | Review and ship | Diff review, reconciliation against GOLD, deploy |

Four vignettes ship in [`demo_prompts.md`](demo_prompts.md):

1. **"Who owes us money?"**: a net-new Collections Cockpit (AR aging, DSO, disputes).
2. **"Our supplier is slipping"**: replace a Tableau supplier scorecard and find the declining supplier.
3. **"Transfer instead of buy"**: a daily transfer-vs-reorder decision app across plants.
4. **"Add the why"**: enhance an existing app with a root-cause tab.

The data has these stories built in so the "aha" moments are reliable. Finished reference answers live in
[`examples/`](examples/README.md).

> All company, plant, supplier, customer and people names are invented. Any resemblance to real organizations is
> coincidental.

## 2. Repository layout

| Path | What it is |
|---|---|
| `demo_prompts.md` | The demo script: 4 vignettes with Explore and Plan prompts |
| `setup/load_raw.sql` | **Fast setup:** creates the database and loads RAW from Parquet |
| `data/raw/*.parquet` | RAW layer snapshot (29 tables, about 72K rows, about 1.5 MB) |
| `generator/` | Python generator that produces fresh data ending yesterday ([README](generator/README.md)) |
| `dbt_ironclad/` | dbt project: RAW → BRONZE (views) → SILVER → GOLD (tables): 57 models, 1 snapshot, 110 tests |
| `examples/` | Reference outputs (apps and SQL) for each vignette |
| `apps/` | Where the live demo writes new apps (the prompts target `apps/<usecase>/`) |
| `setup/export_raw.py` | Maintainer only: re-export the Parquet snapshot |

## 3. Setup

**You need:**
- A Snowflake account with Cortex Code enabled.
- A role that can create a database.
- A warehouse (XS is plenty).
- The `SNOWFLAKE.CORTEX_USER` (or `CORTEX_AGENT_USER`) database role, which goes to `PUBLIC` by default.

All objects live in one database, `"STREAMLIT-CORTEX-20261018"`. The hyphens are intentional, so keep the double quotes.

### 3a. (Recommended) Create a lab role instead of using ACCOUNTADMIN

```sql
USE ROLE ACCOUNTADMIN;
CREATE ROLE IF NOT EXISTS IRONCLAD_LAB_ROLE;
GRANT CREATE DATABASE ON ACCOUNT TO ROLE IRONCLAD_LAB_ROLE;
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE IRONCLAD_LAB_ROLE;          -- or your warehouse
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE IRONCLAD_LAB_ROLE;
GRANT ROLE IRONCLAD_LAB_ROLE TO USER <your_user>;
-- To deploy the Streamlit apps, also grant CREATE STREAMLIT on the target schema
-- (and usage on a compute pool if you use Container Runtime).
```

`dbt_ironclad/profiles.yml` uses `IRONCLAD_LAB_ROLE` and `COMPUTE_WH`. Edit them if yours differ.

### 3b. Load the data: pick one

**Option A: load the Parquet snapshot (about 1 minute, no Python).**
1. Bring this folder into a Snowsight Workspace (*Projects » Workspaces » Create / From Git repository*, or upload the
   folder). You can also work from a local clone with the Snowflake CLI.
2. Open `setup/load_raw.sql` and run it. Step 2 offers three ways to put the files on the stage:
   - `COPY FILES` from the Workspace,
   - `snow stage copy`,
   - the Snowsight upload UI.
3. Build the models (see 3c).

The snapshot's last day is **2026-10-18**. The prompts say "today" and "the last 90 days", and the data answers relative
to its own latest date, so the stories still work. To move the window up to yesterday, run the generator *after* loading.
It tops up only the missing days.

**Option B: generate fresh data (a few minutes).**

```sql
CREATE DATABASE IF NOT EXISTS "STREAMLIT-CORTEX-20261018";
CREATE SCHEMA  IF NOT EXISTS "STREAMLIT-CORTEX-20261018".RAW;
```

Then run `generator/generate.py`, either from a Workspace or with `python generator/generate.py` locally. The run ends with
19 integrity checks, and all of them should print `0`. Details: [`generator/README.md`](generator/README.md).

### 3c. Build BRONZE / SILVER / GOLD with dbt

- **Snowsight Workspace:** open `dbt_ironclad/`, then pick **Build** from the dbt toolbar (or deploy it as a dbt Project on Snowflake).
- **CLI:** `cd dbt_ironclad && dbt build` (dbt-snowflake; use your own auth in `profiles.yml`).

Expect `PASS=168 WARN=0 ERROR=0`.

### 3d. Smoke test

```sql
SELECT COUNT(*) FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_AR_OPEN_ITEMS_AGING;     -- ~2.9K
SELECT COUNT(*) FROM "STREAMLIT-CORTEX-20261018".GOLD.FCT_TRANSFER_VS_REORDER;     -- ~470
```

## 4. Running the demo with Cortex Code

Open [`demo_prompts.md`](demo_prompts.md) and paste the prompts **in order**. Each one builds on what the previous one
found. The Explore prompts deliberately avoid table names, so the agent has to discover them. Compare results with
[`examples/`](examples/README.md). Each example app has a `reconciliation.sql` that proves its KPIs match GOLD.

### In Snowsight (CoCo in Snowsight)

1. Open the project in **Projects » Workspaces**. CoCo uses the open workspace files as context and writes new
   files there (e.g. `apps/collections/`).
2. Open the CoCo panel with the CoCo icon in the lower-right corner. Set the role and warehouse in the context selector.
3. Paste an **Explore** prompt, then the **Plan** prompt. Plan prompts start with *"Plan only / Don't write code yet"*.
   CoCo presents a plan card, and you choose to proceed, modify or cancel. Review the proposed edits in the diff view.
4. Use `@` to point at a specific file or table (e.g. `@apps/collections/streamlit_app.py` for Vignette 4).
5. Deploy a generated app from its folder (`snowflake.yml`). Set the warehouse and compute pool in *App Settings*.

### In CoCo Desktop (or the CoCo CLI)

1. Install [CoCo Desktop](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-desktop) (macOS/Windows) or
   the [CoCo CLI](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-cli)
   (`curl -LsS https://ai.snowflake.com/static/cc-scripts/install.sh | sh`, then run `cortex`).
2. Sign in, or pick a connection from `~/.snowflake/connections.toml` (shared with the Snowflake CLI).
3. Open this folder (a local clone) as the working directory so CoCo can read and write `apps/` and `explore/`.
4. Run the same prompts. Use **Plan mode** for the Plan prompts. Desktop and the CLI can also run `dbt build`,
   the generator, and `snow streamlit deploy` from the integrated terminal.
5. Optional: restrict the session to read-only for the Explore steps (`/guardrails` in the CLI, or **+ » Restrict
   this session** in Desktop).

### Facilitator tips

- Run the Explore prompts first; the Plan prompts reference files saved during exploration (`explore/*.sql`).
- If a live run goes sideways, open the matching folder in `examples/`.
- Vignette 4 edits the Vignette 1 app. Keep a copy if you want to show the before and after.
- Reset between sessions: recreate the four schemas and reload (see [`generator/README.md`](generator/README.md#reset)).

## 5. Security notes

- No credentials, account identifiers or user names are stored in this repo.
  - Apps use the Streamlit Snowflake connection.
  - The generator uses the active Snowpark session or an OAuth token file plus environment variables.
  - `profiles.yml` has empty `account`/`user` fields; dbt in Snowflake uses the session.
- Apps and examples are read-only against GOLD. No DDL or DML in app code.
- `.gitignore` excludes dbt `target/` and `logs/`, Python caches, virtual envs, `.env`, key files and local
  Snowflake connection files. Don't commit `~/.snowflake/connections.toml` or private keys.
- Use a dedicated lab role (3a), not ACCOUNTADMIN, when running this with customers.
