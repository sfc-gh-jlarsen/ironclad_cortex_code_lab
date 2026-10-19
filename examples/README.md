# Examples

Finished reference outputs for the demo vignettes in [`../demo_prompts.md`](../demo_prompts.md).
Each example is what a vignette should produce when you run its **Explore → Plan → Code → Commit** prompts.
Use them as the answer key during a live demo, or as a fallback if a live run goes sideways.

## How this repo fits together

| Path | What it is |
|---|---|
| `README.md` | Project overview, setup, and how to run the prompts in CoCo (Snowsight and Desktop/CLI). |
| `setup/`, `data/raw/` | Fast setup: `load_raw.sql` loads the RAW layer from the shipped Parquet snapshot. |
| `generator/` | Python generator for the fictional **Ironclad Tire & Rubber Co.** data (`generate.py`, `master_data.py`). Loads RAW with fresh dates. See `generator/README.md`. |
| `dbt_ironclad/` | dbt project that builds RAW → BRONZE → SILVER → GOLD in `"STREAMLIT-CORTEX-20261018"`. |
| `demo_prompts.md` | The demo script: 4 vignettes, each with Explore prompts and one Plan prompt. |
| `examples/` | The finished output for each vignette (this folder). |

Demo setup order: load the Parquet (`setup/load_raw.sql`) or run the generator → `dbt build` → walk through a vignette in `demo_prompts.md` → compare with `examples/`.

## Layout

```
examples/
  apps/<usecase>/   Streamlit app built from the vignette's Plan prompt
  sql/<usecase>/    SQL saved during the vignette's Explore prompts
```

Note: the prompts in `demo_prompts.md` tell the agent to write to `apps/<usecase>/` and
`explore/*.sql` at the workspace root. That is intentional — the live demo builds fresh;
`examples/` holds the saved reference copy.

## Examples (one per vignette)

| # | Vignette | Use case | App | SQL | Status |
|---|---|---|---|---|---|
| 1 | "Who owes us money?" — net-new Collections Cockpit | `collections` | `apps/collections/` | `sql/collections/ar_aging_analysis.sql` | Done |
| 2 | "Our supplier is slipping" — replace Tableau scorecard | `supplier_scorecard` | `apps/supplier_scorecard/` | `sql/supplier_scorecard/supplier_otd_analysis.sql` | Done |
| 3 | "Transfer instead of buy" — daily transfer-vs-reorder | `transfer_planner` | `../apps/transfer_planner/` (see note) | `sql/transfer_planner/transfer_analysis.sql` | Done |
| 4 | "Add the why" — Root Cause tab on Collections | `collections` (enhancement) | `apps/collections/` (Root Cause tab) | `sql/collections/root_cause_analysis.sql` | Done |

Vignette 4 enhances the Vignette 1 app rather than creating a new one, so there are 3 apps across 4 examples.
`examples/apps/collections/` is the **after** state (Dashboard, Dispute report, and Root Cause tabs). To demo the
"before", hide or remove the Root Cause tab in a copy before running Vignette 4.

Note: the Vignette 3 reference app currently lives at the workspace root in `../apps/transfer_planner/` (where the live
prompt writes it), with its `reconciliation.sql`. Copy it to `examples/apps/transfer_planner/` if you want the root
`apps/` folder empty for a fresh live run.

Story numbers quoted in the example SQL comments (e.g. ~$5.03M net avoidable, Meridian = 80.9% of Valle Alto carbon
black spend) match the shipped Parquet snapshot (last day 2026-10-18). Regenerating data shifts the dates, and amounts
may move slightly.

## Conventions for new examples

- Read only from the GOLD schema; no DDL/DML in apps.
- No hard-coded credentials; use the Streamlit Snowflake connection.
- Cache queries; keep business logic in SQL/dbt, not Python.
- Include a `reconciliation.sql` that proves app KPIs match GOLD.
- Each app folder has its own `snowflake.yml` (update the `identifier` before deploying to a new account).
