select wholesaler, invoice_no, line_no, count(*) as copies
from {{ ref('fct_sales') }}
group by all
having count(*) > 1
