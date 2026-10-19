select
    p.plant_id,
    p.plant_name,
    p.city,
    p.region,
    p.country_code,
    p.latitude,
    p.longitude,
    p.company_code,
    c.company_name,
    c.currency_code                                   as local_currency_code,
    case p.country_code when 'US' then 'North America' when 'MX' then 'North America' else 'Europe' end as plant_region_group
from {{ ref('stg_sap__plants') }} p
join {{ ref('stg_sap__company_codes') }} c on c.company_code = p.company_code
