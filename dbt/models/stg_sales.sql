-- Every line of every weekly file loaded by the Lambda (silver layer).
-- Files are cumulative, so the same sale appears in many files here.
select *
from read_json(
    's3://{{ var("lake_bucket") }}/silver/sales/*/*.jsonl.gz',
    format = 'newline_delimited',
    columns = {
        wholesaler: 'VARCHAR', invoice_no: 'VARCHAR', line_no: 'INTEGER', invoice_date: 'DATE',
        product_code: 'VARCHAR', product_source_name: 'VARCHAR', locality_code: 'VARCHAR',
        locality_source_name: 'VARCHAR', quantity: 'INTEGER', amount_xof: 'DOUBLE',
        source_file: 'VARCHAR', file_week: 'VARCHAR'
    }
)
