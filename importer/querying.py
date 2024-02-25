import weaviate
import weaviate.classes as wvc

import time
import sys
import os
import requests
import random
from loguru import logger
from threading import Thread
import numpy as np
from prometheus_client import start_http_server, Summary, Gauge, Counter

vector_query = Summary("vector_query_seconds", "duration of a single vector query")
querying_tenants = Gauge(
    "querying_tenants_total",
    "number of tenants that currently have users querying them",
)
querying_users = Gauge(
    "querying_users_total",
    "number of users (across tenants) who are currently sending queries",
)
query_result = Counter(
    "query_result_total",
    "duration of a single vector query",
    ["result"],
)

replication = False
if os.getenv("REPLICATION") is not None and os.getenv("REPLICATION") == "true":
    replication = True


def do():
    prometheus_port = int(os.getenv("PROMETHEUS_PORT") or 8000)
    start_http_server(prometheus_port)

    host = os.getenv("HOST")
    host_grpc = os.getenv("HOST_GRPC")
    no_of_tenants = int(os.getenv("TENANTS") or 10)
    vector_dimensions = int(os.getenv("VECTOR_DIMENSIONS") or 1536)

    parallel_queries_per_tenant = int(os.getenv("PARALLEL_QUERIES_PER_TENANT") or 3)
    queries_per_tenant = int(os.getenv("QUERIES_PER_TENANT") or 1000)
    query_frequency_per_minute = int(os.getenv("QUERY_FREQUENCY_PER_MINUTE") or 30)

    client = weaviate.connect_to_custom(
        http_host=host,
        http_port=80,
        http_secure=False,
        grpc_host=host_grpc,
        grpc_port=50051,
        grpc_secure=False,
    )

    all_tenants = build_tenant_list(client)
    tenants = pick_tenants(all_tenants, no_of_tenants)
    unique_tenants = len(tenants)
    tenants = tenants * parallel_queries_per_tenant

    querying_tenants.inc(unique_tenants)
    query_in_parallel(
        client,
        tenants,
        queries_per_tenant,
        query_frequency_per_minute,
        vector_dimensions,
    )
    querying_tenants.dec(unique_tenants)

    # stick around for another 30s doing nothing, so we can make sure all
    # metrics are scraped
    time.sleep(30)


def query_in_parallel(
    client: weaviate.WeaviateClient, tenants, total, qpm, vector_dimensions
):
    threads = []
    for tenant in tenants:
        t = Thread(target=query, args=[client, tenant, total, qpm, vector_dimensions])
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def query(client: weaviate.WeaviateClient, tenant, total, qpm, vector_dimensions):
    col = client.collections.get("MultiTenancyTest").with_tenant(tenant)
    if replication:
        col = col.with_consistency_level(wvc.ConsistencyLevel.ONE)
    avg_wait = 60 / qpm
    querying_users.inc()
    for i in range(total):
        wait = 2 * random.random() * avg_wait
        time.sleep(wait)
        before = time.time()
        result = None
        fail = False
        try:
            res = col.query.near_vector(
                np.random.rand(1, vector_dimensions)[0].tolist(), limit=10
            )

            if len(res.objects) != 10:
                logger.error(f"Missing results. Requested 10, but got {res_len}")
                fail = True
        except Exception as e:
            logger.error(e)
            fail = True
        took = time.time() - before
        vector_query.observe(took)

        if fail:
            query_result.labels(result="failure").inc()
        else:
            query_result.labels(result="success").inc()

        if i % 100 == 0:
            print(f"progress: {i}/{total} for tenant={tenant}")
    querying_users.dec()


def build_tenant_list(client: weaviate.WeaviateClient):
    tenants = list(client.collections.get("MultiTenancyTest").tenants.get().keys())
    return tenants


def pick_tenants(tenants, no_of_tenants):
    return [random.choice(tenants) for i in range(no_of_tenants)]


do()
