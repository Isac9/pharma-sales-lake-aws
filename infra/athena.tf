# Real AWS only (Glue and Athena are not in the free LocalStack edition):
# the gold Parquet files become a SQL table queryable with Athena.

resource "aws_glue_catalog_database" "gold" {
  count = var.localstack ? 0 : 1
  name  = "pharma_gold"
}

resource "aws_glue_catalog_table" "fct_sales" {
  count         = var.localstack ? 0 : 1
  database_name = aws_glue_catalog_database.gold[0].name
  name          = "fct_sales"
  table_type    = "EXTERNAL_TABLE"
  parameters    = { classification = "parquet" }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.lake.id}/gold/fct_sales/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }
    dynamic "columns" {
      for_each = {
        wholesaler   = "string", invoice_no = "string", line_no = "int", invoice_date = "date",
        product_code = "string", product_source_name = "string", locality_code = "string",
        quantity     = "int", amount_xof = "double", source_file = "string", file_week = "string"
      }
      content {
        name = columns.key
        type = columns.value
      }
    }
  }
}

resource "aws_athena_workgroup" "pharma" {
  count         = var.localstack ? 0 : 1
  name          = "pharma"
  force_destroy = true
  configuration {
    result_configuration {
      output_location = "s3://${aws_s3_bucket.lake.id}/athena-results/"
    }
  }
}
