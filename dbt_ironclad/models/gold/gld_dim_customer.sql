{{ config(materialized='view', alias='dim_customer') }}
-- Gold-facing conformed dimension (built in silver)
select * from {{ ref('dim_customer') }}
