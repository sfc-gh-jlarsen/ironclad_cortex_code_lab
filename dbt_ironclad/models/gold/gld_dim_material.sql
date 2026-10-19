{{ config(materialized='view', alias='dim_material') }}
-- Gold-facing conformed dimension (built in silver)
select * from {{ ref('dim_material') }}
