{{ config(materialized='view') }}

-- Bronze: FX_RATES (reference) -> business-friendly names and types
select
    RATE_DATE as rate_date,
    FROM_CURRENCY as from_currency,
    TO_CURRENCY as to_currency,
    EXCHANGE_RATE::number(18,6) as units_per_usd,
    RATE_SOURCE as rate_source
from {{ source('reference', 'FX_RATES') }}
qualify row_number() over (partition by RATE_DATE, TO_CURRENCY order by RATE_DATE, TO_CURRENCY) = 1
