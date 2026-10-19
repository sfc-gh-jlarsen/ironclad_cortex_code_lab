-- SCD2 customer history from the snapshot
select
    dbt_scd_id                               as customer_version_id,
    customer_id,
    customer_name,
    city,
    region,
    country_code,
    customer_segment,
    company_code,
    payment_terms_code,
    payment_terms_days,
    credit_limit,
    customer_since_date,
    dbt_valid_from                           as valid_from,
    dbt_valid_to                             as valid_to,
    dbt_valid_to is null                     as is_current
from {{ ref('snap_customers') }}
