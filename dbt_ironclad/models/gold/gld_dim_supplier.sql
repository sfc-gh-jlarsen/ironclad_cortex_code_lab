{{ config(materialized='view', alias='dim_supplier') }}
-- Gold-facing conformed dimension (built in silver)
select * from {{ ref('dim_supplier') }}
