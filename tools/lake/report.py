"""Why deduplication matters: summing every cumulative file vs the deduplicated gold table."""
import os

import duckdb

from .aws import LAKE_BUCKET


def connect():
    con = duckdb.connect()
    con.execute("load httpfs")
    endpoint = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:  # LocalStack
        con.execute(f"set s3_endpoint='{endpoint.split('://')[1]}'; set s3_url_style='path'; set s3_use_ssl=false;"
                    "set s3_access_key_id='test'; set s3_secret_access_key='test'; set s3_region='us-east-1';")
    return con


def main():
    con = connect()
    silver = f"s3://{LAKE_BUCKET}/silver/sales/*/*.jsonl.gz"
    gold = f"s3://{LAKE_BUCKET}/gold/fct_sales/fct_sales.parquet"
    con.sql(f"""
        with naive as (select wholesaler, count(*) as rows, sum(amount_xof) as amount
                       from read_json('{silver}', format='newline_delimited') group by 1),
             gold as  (select wholesaler, count(*) as rows, sum(amount_xof) as amount
                       from read_parquet('{gold}') group by 1)
        select n.wholesaler,
               n.rows                          as rows_all_files,
               g.rows                          as rows_deduplicated,
               round(n.amount / 1e6, 1)        as naive_revenue_m_xof,
               round(g.amount / 1e6, 1)        as true_revenue_m_xof,
               round(n.amount / g.amount, 1)   as overstatement_x
        from naive n join gold g using (wholesaler) order by 1
    """).show()


if __name__ == "__main__":
    main()
