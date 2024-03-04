import weaviate
import weaviate.classes as wvc
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
host_grpc = os.getenv("HOST_GRPC")

client = weaviate.connect_to_custom(
    http_host=host,
    http_port=80,
    http_secure=False,
    grpc_host=host_grpc,
    grpc_port=50051,
    grpc_secure=False,
)

total_tenants = int(os.getenv("TOTAL_TENANTS"))
tenants_per_cycle = int(os.getenv("TENANTS_PER_CYCLE"))
objects_per_tenant = int(os.getenv("OBJECTS_PER_TENANT"))
prometheus_port = int(os.getenv("PROMETHEUS_PORT") or 8000)
implicit_ratio = float(os.getenv("IMPLICIT_TENANT_RATIO"))
vector_dimensions = int(os.getenv("VECTOR_DIMENSIONS") or 1536)


def random_name(length):
    letters = string.ascii_lowercase
    return "".join(random.choice(letters) for i in range(length))


def do(client: weaviate.WeaviateClient):
    start_http_server(prometheus_port)

    tenants_added = Counter("tenants_added_total", "Number of tenants added.")
    tenants_added_implicitly = Counter(
        "tenants_added_implicitly_total", "Number of tenants added."
    )
    objects_added = Counter("objects_added_total", "Number of objects added.")
    tenants_batch = Summary("tenant_batch_seconds", "Duration it took to add tenants")
    objects_batch = Summary("objects_batch_seconds", "Duration it took to add objects")
    i = 0
    col = client.collections.get("MultiTenancyTest")

    # reduce concurrency of all runners starting at the same time, start with
    # random offset
    time.sleep(random.random() * 5)
    while i < total_tenants:
        # create next batch of tenants
        tenant_names = [f"{random_name(24)}" for j in range(tenants_per_cycle)]
        new_tenants = [wvc.tenants.Tenant(name=t) for t in tenant_names]

        implicit = random.random() <= implicit_ratio

        if implicit:
            logger.info(f"did not create any tenants this round (implicit batch)")
            tenants_added_implicitly.inc(tenants_per_cycle)
        else:
            before = time.time()
            for attempt in range(100):
                try:
                    col.tenants.create(new_tenants)
                    break
                except Exception as e:
                    logger.error(e)
                    sleep = random.randrange(0, 5000)
                    logger.info(f"sleep {sleep}ms, then retry {attempt}")
                    time.sleep(sleep / 1000)
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


def load_records(client: weaviate.WeaviateClient, tenant_names):
    for tenant in tenant_names:
        with client.batch.fixed_size(100, 4) as batch:
            for i in range(objects_per_tenant):
                batch.add_object(
                    "MultiTenancyTest",
                    {
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
                    vector=np.random.rand(1, vector_dimensions)[0].tolist(),
                )
        errors = client.batch.failed_objects
        if len(errors) > 0:
            for error in errors:
                logger.error(error)
        # logger.debug(f"Imported {objects_per_tenant} objs for tenant {tenant}")


do(client)
