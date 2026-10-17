{{ config(materialized='external', location='s3://' ~ var('lake_bucket') ~ '/gold/sales_by_product_week/sales_by_product_week.parquet') }}

select
    strftime(invoice_date, '%G-W%V') as iso_week,
    product_code,
    wholesaler,
    sum(quantity)                    as quantity,
    sum(amount_xof)                  as amount_xof
from {{ ref('fct_sales') }}
group by all
