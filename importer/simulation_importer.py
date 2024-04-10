import os
import weaviate
import weaviate.classes as wvc
import datetime
import random
import uuid
import numpy as np
from loguru import logger

col_name = "TenaciousT"  # this is not the best collection in the world – this is just a tribute
ttl_col_name = "TTL"
ttl = 90  # seconds

host = os.getenv("HOST") or "localhost"
port = int(os.getenv("PORT") or 8080)
host_grpc = os.getenv("HOST_GRPC") or "localhost"
port_grpc = int(os.getenv("PORT_GRPC") or 50051)
prometheus_port = int(os.getenv("PROMETHEUS_PORT") or 8000)


min_tenant_id = int(os.getenv("MIN_TENANT_ID") or 0)
max_tenant_id = int(os.getenv("MAX_TENANT_ID") or 10_000)
objects_per_tenant = int(os.getenv("OBJECTS_PER_TENANT") or 1000)
tenants_per_cycle = int(os.getenv("TENANTS_PER_CYCLE") or 50)
vector_dimensions = int(os.getenv("VECTOR_DIMENSIONS") or 1536)

client = weaviate.connect_to_custom(
    http_host=host,
    http_port=port,
    http_secure=False,
    grpc_host=host_grpc,
    grpc_port=port_grpc,
    grpc_secure=False,
)


def tenant_name(id: int) -> str:
    return f"tenant_{id:010d}"


def import_loop():
    primary_col = client.collections.get(col_name)
    ttl_col = client.collections.get(ttl_col_name)

    lower = min_tenant_id
    while True:
        if lower > max_tenant_id:
            # start over
            lower = min_tenant_id

        upper = lower + tenants_per_cycle
        if upper > max_tenant_id:
            upper = max_tenant_id

        add_ttl_for_tenants(ttl_col, lower, upper)
        import_tenants_batch(primary_col, lower, upper)
        logger.info(f"completed batch {tenant_name(lower)}-{tenant_name(upper)}")

        lower += tenants_per_cycle


def import_tenants_batch(
    primary_col: weaviate.collections.Collection, lower: int, upper: int
):
    tenants = [wvc.tenants.Tenant(name=tenant_name(tid)) for tid in range(lower, upper)]

    primary_col.tenants.create(tenants)
    for tenant in tenants:
        col_t = primary_col.with_tenant(tenant)
        import_data_batch(col_t)


def import_data_batch(col_t):
    with col_t.batch.dynamic() as batch:
        for i in range(objects_per_tenant):
            batch.add_object(
                {
                    "int1": random.randint(0, 10000),
                    "int2": random.randint(0, 10000),
                    "number1": random.random(),
                    "number2": random.random(),
                    "text1": f"{random.randint(0, 10000)}",
                    "text2": f"{random.randint(0, 10000)}",
                },
                vector=np.random.rand(1, vector_dimensions)[0].tolist(),
                # use deterministic ids, so future iterations automatically
                # turn into updates
                uuid=uuid.UUID(int=i),
            )
    if len(client.batch.failed_objects) > 0:
        logger.error(client.batch.failed_objects)


def add_ttl_for_tenants(
    ttl_col: weaviate.collections.Collection, lower: int, upper: int
):
    expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=ttl
    )

    with ttl_col.batch.fixed_size(1000) as batch:
        for tid in range(lower, upper):
            batch.add_object(
                properties={
                    "tenant_name": tenant_name(tid),
                    "expiration": expiration.isoformat(),
                }
            )

    if len(client.batch.failed_objects) > 0:
        logger.error(client.batch.failed_objects)


import_loop()
client.close()
