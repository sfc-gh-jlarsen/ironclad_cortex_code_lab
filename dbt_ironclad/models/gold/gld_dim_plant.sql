{{ config(materialized='view', alias='dim_plant') }}
-- Gold-facing conformed dimension (built in silver)
select * from {{ ref('dim_plant') }}
