{{ config(materialized='external', location='s3://' ~ var('lake_bucket') ~ '/gold/fct_sales/fct_sales.parquet') }}

-- Gold layer: one row per invoice line. When a line is in several cumulative files,
-- keep the most recent version of it.
select
    wholesaler, invoice_no, line_no, invoice_date, product_code, product_source_name,
    locality_code, quantity, amount_xof, source_file, file_week
from {{ ref('stg_sales') }}
qualify row_number() over (partition by wholesaler, invoice_no, line_no order by file_week desc) = 1
