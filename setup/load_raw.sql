-- Ironclad Tire & Rubber Co. lab: load the RAW layer from the Parquet files in data/raw/
-- (the fast path; alternative is `python generator/generate.py`). Run as a role that can create a database.
--
-- Step 1 creates the database, schemas, stage, and file format.
-- Step 2 puts the 29 Parquet files on the stage (pick ONE option).
-- Step 3 creates every RAW table from the Parquet schema and loads it.
-- Then run `dbt build` in dbt_ironclad/ to build BRONZE / SILVER / GOLD.

-- 1) Containers ----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS "STREAMLIT-CORTEX-20261018";
CREATE SCHEMA IF NOT EXISTS "STREAMLIT-CORTEX-20261018".RAW;
CREATE SCHEMA IF NOT EXISTS "STREAMLIT-CORTEX-20261018".BRONZE;
CREATE SCHEMA IF NOT EXISTS "STREAMLIT-CORTEX-20261018".SILVER;
CREATE SCHEMA IF NOT EXISTS "STREAMLIT-CORTEX-20261018".GOLD;
CREATE STAGE IF NOT EXISTS "STREAMLIT-CORTEX-20261018".RAW.SEED_STAGE;
CREATE FILE FORMAT IF NOT EXISTS "STREAMLIT-CORTEX-20261018".RAW.SEED_PARQUET TYPE = PARQUET;

-- 2) Get the files onto the stage. Choose ONE:
--   a) Snowsight Workspace (this project is in a Workspace): copy straight from the workspace.
--      Replace <workspace> with your workspace name (Workspace menu > Copy path / see README).
-- COPY FILES INTO @"STREAMLIT-CORTEX-20261018".RAW.SEED_STAGE
--   FROM 'snow://workspace/USER$.PUBLIC."<workspace>"/versions/live/data/raw/';
--
--   b) Snowflake CLI from a local clone:
--      snow stage copy data/raw/ '@"STREAMLIT-CORTEX-20261018".RAW.SEED_STAGE' --overwrite
--
--   c) Snowsight UI: Data > Databases > STREAMLIT-CORTEX-20261018 > RAW > Stages > SEED_STAGE
--      > + Files, and drag in everything from data/raw/.

LIST @"STREAMLIT-CORTEX-20261018".RAW.SEED_STAGE;   -- expect 29 .parquet files

-- 3) Create + load each table (idempotent: re-running replaces the RAW tables)
EXECUTE IMMEDIATE $$
DECLARE
  tables ARRAY := ARRAY_CONSTRUCT(
    'AR_DISPUTES', 'BSID_BSAD', 'EINA', 'EKBE', 'EKKO', 'EKPO', 'FX_RATES', 'GEN_LOAD_LOG', 'KNA1', 'LFA1',
    'LIKP', 'LIPS', 'MARA', 'MARC', 'MARD', 'PAYMENTS', 'RBKP', 'RSEG', 'SUP_QUALITY_INSPECTIONS',
    'SUP_RISK_SCORES', 'T001', 'T001W', 'VBAK', 'VBAP', 'VBRK', 'VBRP', 'WMS_STOCK_TRANSFERS',
    'WMS_TRANSFER_LANES', 'WMS_TRANSFER_RECEIPTS');
  t STRING;
  loaded INTEGER := 0;
BEGIN
  FOR i IN 0 TO ARRAY_SIZE(:tables) - 1 DO
    t := GET(:tables, :i)::STRING;
    EXECUTE IMMEDIATE
      'CREATE OR REPLACE TABLE "STREAMLIT-CORTEX-20261018".RAW.' || t || ' USING TEMPLATE (' ||
      'SELECT ARRAY_AGG(OBJECT_CONSTRUCT(*)) WITHIN GROUP (ORDER BY ORDER_ID) FROM TABLE(INFER_SCHEMA(' ||
      'LOCATION => ''@"STREAMLIT-CORTEX-20261018".RAW.SEED_STAGE'', FILES => ''' || t || '.parquet'', ' ||
      'FILE_FORMAT => ''"STREAMLIT-CORTEX-20261018".RAW.SEED_PARQUET'')))';
    EXECUTE IMMEDIATE
      'COPY INTO "STREAMLIT-CORTEX-20261018".RAW.' || t ||
      ' FROM @"STREAMLIT-CORTEX-20261018".RAW.SEED_STAGE FILES = (''' || t || '.parquet'')' ||
      ' FILE_FORMAT = (FORMAT_NAME = ''"STREAMLIT-CORTEX-20261018".RAW.SEED_PARQUET'')' ||
      ' MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE';
    loaded := loaded + 1;
  END FOR;
  RETURN 'Loaded ' || loaded || ' RAW tables';
END;
$$;

-- 4) Sanity check: expect 29 tables, ~72K rows
SELECT COUNT(*) AS tables, SUM(row_count) AS total_rows
FROM "STREAMLIT-CORTEX-20261018".INFORMATION_SCHEMA.TABLES
WHERE table_schema = 'RAW' AND table_type = 'BASE TABLE';
