-- Current customer view (type 1) + behavioral attributes useful for slicing
select
    h.customer_id,
    h.customer_name,
    h.city,
    h.region,
    h.country_code,
    h.customer_segment,
    h.company_code,
    h.payment_terms_code,
    h.payment_terms_days,
    h.credit_limit,
    h.customer_since_date,
    datediff(year, h.customer_since_date, current_date())   as tenure_years
from {{ ref('dim_customer_history') }} h
where h.is_current
