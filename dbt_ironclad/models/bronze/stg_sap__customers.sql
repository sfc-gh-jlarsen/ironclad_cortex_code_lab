{{ config(materialized='view') }}

-- Bronze: KNA1 (sap) -> business-friendly names and types
select
    KUNNR as customer_id,
    NAME1 as customer_name,
    ORT01 as city,
    REGIO as region,
    LAND1 as country_code,
    KTOKD as account_group,
    DECODE(KTOKD, 'ZOEM', 'OEM', 'ZDLR', 'Replacement Dealer', 'ZFLT', 'Commercial Fleet') as customer_segment,
    BUKRS as company_code,
    ZTERM as payment_terms_code,
    TRY_TO_NUMBER(REGEXP_SUBSTR(ZTERM, '[0-9]+')) as payment_terms_days,
    KLIMK::number(18,2) as credit_limit,
    ERDAT as customer_since_date,
    LOADED_AT as loaded_at
from {{ source('sap', 'KNA1') }}
qualify row_number() over (partition by KUNNR order by KUNNR) = 1
