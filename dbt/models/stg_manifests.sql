-- One manifest per loaded file, written by the Lambda: rows and amount counted in the source file.
select *
from read_json(
    's3://{{ var("lake_bucket") }}/manifests/*/*.json',
    columns = {wholesaler: 'VARCHAR', file_week: 'VARCHAR', rows: 'INTEGER', amount_xof: 'DOUBLE', source_file: 'VARCHAR'}
)
