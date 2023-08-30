import weaviate
import time
import random
import sys
import numpy as np
import uuid
import os
import requests
import string
from loguru import logger
from typing import Optional
from prometheus_client import start_http_server, Counter, Summary


host = os.getenv("HOST")
client = weaviate.Client(f"http://{host}", timeout_config=(20, 240))

total_tenants = int(os.getenv("TOTAL_TENANTS"))
tenants_per_cycle = int(os.getenv("TENANTS_PER_CYCLE"))
objects_per_tenant = int(os.getenv("OBJECTS_PER_TENANT"))
prometheus_port = int(os.getenv("PROMETHEUS_PORT") or 8000)
implicit_ratio = float(os.getenv("IMPLICIT_TENANT_RATIO"))
deactivate_tenants = False
if (
    os.getenv("DEACTIVATE_TENANTS") is not None
    and os.getenv("DEACTIVATE_TENANTS") == "true"
):
    deactivate_tenants = True


def random_name(length):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


def do(client: weaviate.Client):
    start_http_server(prometheus_port)

    tenants_added = Counter("tenants_added_total", "Number of tenants added.")
    tenants_added_implicitly = Counter(
        "tenants_added_implicitly_total", "Number of tenants added."
    )
    objects_added = Counter("objects_added_total", "Number of objects added.")
    tenants_batch = Summary("tenant_batch_seconds", "Duration it took to add tenants")
    objects_batch = Summary("objects_batch_seconds", "Duration it took to add objects")
    i = 0
    while i < total_tenants:
        # create next batch of tenants
        tenant_names = [f"{random_name(24)}" for j in range(tenants_per_cycle)]
        new_tenants = [{"name": t} for t in tenant_names]

        implicit = random.random() <= implicit_ratio

        if implicit:
            logger.info(f"did not create any tenants this round (implicit batch)")
            tenants_added_implicitly.inc(tenants_per_cycle)
        else:
            before = time.time()
            for attempt in range(100):
                res = requests.post(
                    f"http://{host}/v1/schema/MultiTenancyTest/tenants",
                    json=new_tenants,
                )
                if res.status_code != 200:
                    logger.error(res.json())
                    sleep = random.randrange(0, 5000)
                    logger.info(f"sleep {sleep}ms, then retry {attempt}")
                    time.sleep(sleep / 1000)
                else:
                    break
            tenants_added.inc(tenants_per_cycle)
            took = time.time() - before
            tenants_batch.observe(took)
            logger.info(f"created {tenants_per_cycle} tenants in {took}s")

        # create objects across all tenants of batch
        before = time.time()
        load_records(client, tenant_names)
        took = time.time() - before
        logger.info(
            f"import {objects_per_tenant} objects for {tenants_per_cycle} tenants ({objects_per_tenant*tenants_per_cycle} total) took {took}s"
        )

        objects_batch.observe(took)
        objects_added.inc(objects_per_tenant * tenants_per_cycle)
        i += tenants_per_cycle

        if deactivate_tenants:
            before_deactivate = time.time()
            payload = [
                {"name": name, "activityStatus": "COLD"} for name in tenant_names
            ]

            for attempt in range(100):
                res = requests.put(
                    f"http://{host}/v1/schema/MultiTenancyTest/tenants",
                    json=payload,
                )
                if res.status_code != 200:
                    logger.error(res.json())
                    sleep = random.randrange(0, 5000)
                    logger.info(f"sleep {sleep}ms, then retry {attempt}")
                    time.sleep(sleep / 1000)
                else:
                    break
            took = time.time() - before_deactivate
            logger.info(f"deactivated {tenants_per_cycle} tenants in {took}s")


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


def load_records(client: weaviate.Client, tenant_names):
    for tenant in tenant_names:
        client.batch.configure(
            batch_size=1000,
            callback=handle_errors,
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
                    tenant=tenant,
                    vector=np.random.rand(32, 1),
                    class_name="MultiTenancyTest",
                )
        # logger.debug(f"Imported {objects_per_tenant} objs for tenant {tenant}")


do(client)
