{{ config(materialized='view') }}

-- Bronze: weekly third-party supplier risk feed (JSON)
with src as (
    select parse_json(PAYLOAD) as p, FEED_ID, INGESTED_AT
    from {{ source('supplier_portal', 'SUP_RISK_SCORES') }}
    qualify row_number() over (partition by FEED_ID order by INGESTED_AT desc) = 1
)
select
    FEED_ID                                as risk_feed_id,
    p:supplier_id::string                  as supplier_id,
    p:as_of::date                          as score_date,
    p:scores:financial::number(5,1)        as financial_score,
    p:scores:geopolitical::number(5,1)     as geopolitical_score,
    p:scores:esg::number(5,1)              as esg_score,
    p:scores:delivery::number(5,1)         as delivery_score,
    p:overall_score::number(5,1)           as overall_risk_score,
    array_size(p:alerts)                   as alert_count,
    p:alerts                               as alerts,
    INGESTED_AT                            as ingested_at
from src
