select
    material_id,
    material_description,
    material_type,
    case material_type when 'ROH' then 'Raw Material' when 'FERT' then 'Finished Tire' end as material_class,
    material_group                                  as material_category,
    base_uom,
    list_price_usd,
    net_weight_kg,
    product_line,
    tire_size,
    material_group in ('Steel Cord', 'Carbon Black', 'Natural Rubber', 'Synthetic Rubber') as is_critical_material
from {{ ref('stg_sap__materials') }}
