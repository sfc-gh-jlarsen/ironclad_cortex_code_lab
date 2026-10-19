-- Supplier dimension enriched with the latest third-party risk score and sourcing footprint
with latest_risk as (
    select *
    from {{ ref('stg_risk__supplier_risk_scores') }}
    qualify row_number() over (partition by supplier_id order by score_date desc) = 1
),
footprint as (
    select supplier_id,
           count(distinct material_id)                            as materials_supplied,
           count_if(is_primary_source)                            as primary_source_for_count
    from {{ ref('stg_sap__purchasing_info_records') }}
    group by 1
)
select
    s.supplier_id,
    s.supplier_name,
    s.country_code,
    s.city,
    s.account_group,
    s.primary_category,
    iff(s.country_code in ('US', 'MX', 'DE'), 'Regional', 'Overseas')   as sourcing_origin,
    f.materials_supplied,
    f.primary_source_for_count,
    r.score_date                                                       as risk_score_date,
    r.overall_risk_score,
    r.financial_score,
    r.geopolitical_score,
    r.esg_score,
    r.delivery_score,
    r.alert_count                                                      as risk_alert_count,
    case when r.overall_risk_score < 70 then 'High'
         when r.overall_risk_score < 80 then 'Medium' else 'Low' end    as risk_tier
from {{ ref('stg_sap__suppliers') }} s
left join footprint f on f.supplier_id = s.supplier_id
left join latest_risk r on r.supplier_id = s.supplier_id
