-- Files are cumulative: the latest file of each wholesaler holds every sale so far.
-- After deduplication, gold must match it exactly (rows and amount).
with latest as (
    select wholesaler, rows, amount_xof
    from {{ ref('stg_manifests') }}
    qualify row_number() over (partition by wholesaler order by file_week desc) = 1
),

gold as (
    select wholesaler, count(*) as rows, sum(amount_xof) as amount_xof
    from {{ ref('fct_sales') }}
    group by all
)

select l.wholesaler, l.rows as file_rows, g.rows as gold_rows, l.amount_xof as file_amount, g.amount_xof as gold_amount
from latest l
full outer join gold g using (wholesaler)
where l.rows is distinct from g.rows
   or abs(coalesce(l.amount_xof, 0) - coalesce(g.amount_xof, 0)) > 1
