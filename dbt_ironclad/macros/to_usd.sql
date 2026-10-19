-- Macro: convert a local-currency amount to USD using silver.fx_rates_daily (alias fx must be joined)
{% macro to_usd(amount_col, fx_alias='fx') -%}
    round({{ amount_col }} / nullif({{ fx_alias }}.units_per_usd, 0), 2)
{%- endmacro %}
