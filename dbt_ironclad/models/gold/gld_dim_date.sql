{{ config(materialized='view', alias='dim_date') }}
-- Gold-facing conformed dimension (built in silver)
select * from {{ ref('dim_date') }}
