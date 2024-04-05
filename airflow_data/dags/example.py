"""Example ETL"""

from __future__ import annotations

import asyncio
import io
import json
from datetime import datetime
from typing import Any, Callable

from aiohttp import ClientSession, ClientTimeout
from aiohttp.web import HTTPClientError
from airflow.decorators import dag, task
from airflow.hooks.base import BaseHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.amazon.aws.operators.s3 import S3CreateBucketOperator
from airflow.providers.http.operators.http import HttpOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from models.product import Product
from utils import create_uuid_from_string, queue_processing

WEATHER_CONN_NAME = "weather"
WEATHER_PRODUCT_ENDPOINT = "products"
S3_CONN_NAME = "s3"
BUCKET_NAME = "documents"
WORKER_COUNT = 100


async def worker(queue: asyncio.Queue, **kwargs) -> None:
    rows: list = kwargs["data"]
    base_url: str = kwargs["base_url"]
    s3_hook: S3Hook = kwargs["s3_hook"]
    get_message_text_func: Callable = kwargs["get_message_text_func"]

    # auth = BasicAuth(connection_info.username, connection_info.password)
    timeout = ClientTimeout(connect=60, sock_read=60)
    while True:
        item = await queue.get()
        rec = rows[item]
        url = f"{base_url}/{rec['id']}"
        log_message = get_message_text_func(item, url)
        try:
            async with ClientSession(
                # auth=auth,
                timeout=timeout,
            ) as session:
                async with session.get(url, verify_ssl=False) as response:
                    if response.status != 200:
                        rec["sql"] = ""
                        raise HTTPClientError(text=f"Response status = {response.status_code} of {rec['id']}")
                    else:
                        data = await response.json()
                        product = Product(**data)
                        hash_id = create_uuid_from_string(product.product_text)
                        s3_hook.load_file_obj(
                            io.BytesIO(bytes(product.product_text, "ascii")), hash_id, BUCKET_NAME, replace=True
                        )
                        rec["sql"] = f"UPDATE public.product SET product_text='{hash_id}' WHERE id='{product.id}'"
                        print(f"{log_message} success.")

            queue.task_done()
        except Exception as e:
            print("{} failed. {}{}".format(log_message, type(e).__name__, f": {e}" if str(e) else ""))
            raise


@dag(
    schedule="@daily",
    dag_id="example_etl",
    tags=["example"],
    catchup=False,
    doc_md=__doc__,
    start_date=datetime(2021, 1, 1),
)
def taskflow():
    create_table = PostgresOperator(
        task_id="create_table",
        postgres_conn_id="pg_db",
        sql="""
            CREATE TABLE IF NOT EXISTS public.product (
                id VARCHAR PRIMARY KEY,
                wmo_collective_id VARCHAR NULL,
                issuing_office VARCHAR NULL,
                issuance_time VARCHAR NULL,
                product_code VARCHAR NULL,
                product_name VARCHAR NULL,
                product_text VARCHAR NULL
            );
        """,
    )

    drop_table = PostgresOperator(
        task_id="drop_table",
        postgres_conn_id="pg_db",
        sql="DROP TABLE public.product",
    )

    task_get_op = HttpOperator(
        task_id="extract",
        method="GET",
        endpoint=WEATHER_PRODUCT_ENDPOINT,
        http_conn_id=WEATHER_CONN_NAME,
        data={},
        headers={},
        # log_response=True,
        # dag=dag,
    )

    @task(task_id="get_records")
    def get_records(json_string: str) -> list[Product]:
        return [Product(**record).model_dump() for record in json.loads(json_string).get("@graph", [])]

    @task(task_id="transform_records")
    def transform_records(records: list[dict[str, Any]]) -> str:
        values = []
        for rec in records:
            values.append("({})".format(", ".join(f"'{str(v)}'" if v else "null" for v in rec.values())))

        if values:
            return f"INSERT INTO public.product ({', '.join(Product.model_fields)}) VALUES {', '.join(values)};"

    @task(task_id="load_files")
    def load_files(records: list[dict[str, Any]], *args) -> list[dict[str, Any]]:
        connection = BaseHook.get_connection(WEATHER_CONN_NAME)
        base_url = f"{connection.schema}://{connection.host}/{WEATHER_PRODUCT_ENDPOINT}"
        s3_hook = S3Hook(S3_CONN_NAME)

        size = len(records)
        asyncio.run(
            queue_processing(
                (i for i in range(size)),
                worker,
                WORKER_COUNT,
                data=records,
                get_message_text_func=lambda i, u: f"{i + 1}/{size}: download file from {u}",
                base_url=base_url,
                s3_hook=s3_hook,
            )
        )

        return ";\n".join(r["sql"] for r in records)

    records = get_records(task_get_op.output)

    insert_values = PostgresOperator(
        task_id="insert_values",
        postgres_conn_id="pg_db",
        sql=transform_records(records),
    )

    create_bucket = S3CreateBucketOperator(
        task_id="create_bucket",
        bucket_name=BUCKET_NAME,
        aws_conn_id=S3_CONN_NAME,
    )

    update_values = PostgresOperator(
        task_id="update_values",
        postgres_conn_id="pg_db",
        sql=load_files(records, create_bucket.output),
    )

    drop_table >> create_table >> insert_values >> update_values


taskflow()
