{{ config(materialized='view') }}

-- Bronze: supplier portal inspection JSON -> typed columns (one row per inspection lot)
with src as (
    select parse_json(PAYLOAD) as p, INGESTED_AT
    from {{ source('supplier_portal', 'SUP_QUALITY_INSPECTIONS') }}
    qualify row_number() over (partition by INSPECTION_LOT order by INGESTED_AT desc) = 1
)
select
    p:inspection_lot::string                                   as inspection_lot_id,
    p:material_document::string                                as material_document,
    p:po_number::string || '-' || lpad(p:po_item::string, 5, '0') as po_line_id,
    p:supplier_id::string                                      as supplier_id,
    p:material_id::string                                      as material_id,
    p:plant::string                                            as plant_id,
    p:received_qty::number(18,3)                               as received_qty,
    p:sample_size::int                                         as sample_size,
    p:result::string                                           as inspection_result,
    p:rejected_qty::number(18,3)                               as rejected_qty,
    array_size(p:defects)                                      as defect_type_count,
    p:defects[0]:code::string                                  as primary_defect_code,
    p:inspector::string                                        as inspector_id,
    p:inspected_at::timestamp_ntz                              as inspected_at,
    p                                                          as raw_payload,
    INGESTED_AT                                                as ingested_at
from src
