{% snapshot snap_customers %}
{{ config(
    target_schema='SILVER',
    unique_key='customer_id',
    strategy='check',
    check_cols=['customer_name', 'credit_limit', 'payment_terms_code', 'account_group'],
    invalidate_hard_deletes=True
) }}
-- SCD2 history of customer master (credit limit reviews change weekly for some customers)
select customer_id, customer_name, city, region, country_code, account_group, customer_segment,
       company_code, payment_terms_code, payment_terms_days, credit_limit, customer_since_date
from {{ ref('stg_sap__customers') }}
{% endsnapshot %}
