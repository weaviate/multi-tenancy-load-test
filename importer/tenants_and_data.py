import weaviate
import time
import random
import sys
import numpy as np
import uuid
import os
import requests
from loguru import logger
from typing import Optional

host = os.getenv("HOST")
client = weaviate.Client(f"http://{host}", timeout_config=(20, 240))

total_tenants = int(os.getenv("TOTAL_TENANTS"))
tenants_per_cycle = int(os.getenv("TENANTS_PER_CYCLE"))
objects_per_tenant = int(os.getenv("OBJECTS_PER_TENANT"))


def do(client: weaviate.Client):
    i = 0
    while i < total_tenants:
        min_tenant = i
        max_tenant = i + tenants_per_cycle
        # create next batch of tenants
        new_tenants = []
        for t in range(min_tenant, max_tenant):
            new_tenants.append({"name": f"tenant_{t}"})

        before = time.time()
        res = requests.post(
            f"http://{host}/v1/schema/MultiTenancyTest/tenants", json=new_tenants
        )
        took = time.time() - before
        logger.info(f"created {tenants_per_cycle} tenants in {took}s")

        # create objects across all tenants of batch
        before = time.time()
        load_records(client, min_tenant)
        took = time.time() - before
        logger.info(
            f"import {objects_per_tenant} objects for {tenants_per_cycle} tenants ({objects_per_tenant*tenants_per_cycle} total) took {took}s"
        )

        i += tenants_per_cycle


def handle_errors(results: Optional[dict]) -> None:
    """
    Handle error message from batch requests logs the message as an info message.
    Parameters
    ----------
    results : Optional[dict]
        The returned results for Batch creation.
    """

    if results is not None:
        for result in results:
            if (
                "result" in result
                and "errors" in result["result"]
                and "error" in result["result"]["errors"]
            ):
                for message in result["result"]["errors"]["error"]:
                    logger.error(message["message"])


def load_records(client: weaviate.Client, min_tenant):
    for tid in range(min_tenant, min_tenant + tenants_per_cycle):
        tenant = f"tenant_{tid}"
        client.batch.configure(
            batch_size=1000, callback=handle_errors, tenant_key=tenant
        )
        with client.batch as batch:
            for i in range(objects_per_tenant):
                batch.add_data_object(
                    data_object={
                        "tenant_id": tenant,
                        "int1": random.randint(0, 10000),
                        "int2": random.randint(0, 10000),
                        # "int3": random.randint(0, 10000),
                        # "int4": random.randint(0, 10000),
                        # "int5": random.randint(0, 10000),
                        "number1": random.random(),
                        "number2": random.random(),
                        # "number3": random.random(),
                        # "number4": random.random(),
                        # "number5": random.random(),
                        "text1": f"{random.randint(0, 10000)}",
                        "text2": f"{random.randint(0, 10000)}",
                        # "text3": f"{random.randint(0, 10000)}",
                        # "text4": f"{random.randint(0, 10000)}",
                        # "text5": f"{random.randint(0, 10000)}",
                    },
                    vector=np.random.rand(32, 1),
                    class_name="MultiTenancyTest",
                )
        # logger.debug(f"Imported {objects_per_tenant} objs for tenant {tenant}")


do(client)
