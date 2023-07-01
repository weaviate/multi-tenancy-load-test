import weaviate
import time
import sys
import os
import requests
import random
from loguru import logger
from threading import Thread
import numpy as np
from prometheus_client import start_http_server, Summary, Gauge

vector_query = Summary("vector_query_seconds", "duration of a single vector query")
querying_tenants = Gauge(
    "querying_tenants_total",
    "number of tenants that currently have users querying them",
)
querying_users = Gauge(
    "querying_users_total",
    "number of users (across tenants) who are currently sending queries",
)


def do():
    prometheus_port = int(os.getenv("PROMETHEUS_PORT") or 8000)
    start_http_server(prometheus_port)

    host = os.getenv("HOST")
    no_of_tenants = int(os.getenv("TENANTS") or 10)

    parallel_queries_per_tenant = int(os.getenv("PARALLEL_QUERIES_PER_TENANT") or 3)
    queries_per_tenant = int(os.getenv("QUERIES_PER_TENANT") or 1000)
    query_frequency_per_minute = int(os.getenv("QUERY_FREQUENCY_PER_MINUTE") or 30)

    client = weaviate.Client(f"http://{host}", timeout_config=(20, 240))

    all_tenants = build_tenant_list(client)
    tenants = pick_tenants(all_tenants, no_of_tenants)
    unique_tenants = len(tenants)
    tenants = tenants * parallel_queries_per_tenant

    querying_tenants.inc(unique_tenants)
    query_in_parallel(client, tenants, queries_per_tenant, query_frequency_per_minute)
    querying_tenants.dec(unique_tenants)

    # stick around for another 30s doing nothing, so we can make sure all
    # metrics are scraped
    time.sleep(30)


def query_in_parallel(client, tenants, total, qpm):
    threads = []
    for tenant in tenants:
        t = Thread(target=query, args=[client, tenant, total, qpm])
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def query(client, tenant, total, qpm):
    avg_wait = 60 / qpm
    querying_users.inc()
    for i in range(total):
        wait = 2 * random.random() * avg_wait
        time.sleep(wait)
        before = time.time()
        result = (
            client.query.get("MultiTenancyTest", ["int1"])
            .with_limit(10)
            .with_tenant(tenant)
            .with_additional("id")
            .with_near_vector({"vector": np.random.rand(1, 32)})
            .do()
        )
        fail = False
        if "errors" in result:
            fail = True
        else:
            if len(result["data"]["Get"]["MultiTenancyTest"]) != 10:
                fail = True

        took = time.time() - before
        vector_query.observe(took)
        if i % 100 == 0:
            print(f"progress: {i}/{total} for tenant={tenant}")
    querying_users.dec()


def build_tenant_list(client):
    res = client.cluster.get_nodes_status()
    tenants = []
    for node in res:
        for shard in node["shards"]:
            if shard["objectCount"] < 100:
                # tenant was just created, not enough objects to query yet,
                # skip
                continue

            tenants.append(shard["name"])
    return tenants


def pick_tenants(tenants, no_of_tenants):
    return [random.choice(tenants) for i in range(no_of_tenants)]


do()
