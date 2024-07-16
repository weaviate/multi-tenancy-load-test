import os
import random
import uuid
import weaviate
import weaviate.classes as wvc
import numpy as np
from weaviate.collections.classes.tenants import Tenant
from weaviate.classes.query import Filter
import datetime
from loguru import logger
import time

col_name = "TenaciousT"  # this is not the best collection in the world – this is just a tribute
ttl_col_name = "TTL"
tick_interval = 10  # seconds

host = os.getenv("HOST") or "localhost"
port = int(os.getenv("PORT") or 8080)
host_grpc = os.getenv("HOST_GRPC") or "localhost"
port_grpc = int(os.getenv("PORT_GRPC") or 50051)
# prometheus_port = int(os.getenv("PROMETHEUS_PORT") or 8002)

percentage_of_tenants = int(os.getenv("PERCENTAGE_OF_TENANTS") or 30)
objects_per_tenant = int(os.getenv("OBJECTS_PER_TENANT") or 1000)
objects_to_update = int(os.getenv("OBJECTS_TO_UPDATE") or 300)
vector_dimensions = int(os.getenv("VECTOR_DIMENSIONS") or 1536)
ttl = 90  # seconds

client = weaviate.connect_to_custom(
    http_host=host,
    http_port=port,
    http_secure=False,
    grpc_host=host_grpc,
    grpc_port=port_grpc,
    grpc_secure=False,
)

last_execution = time.time()


def user_enabling_loop():
    global last_execution
    ttl_col = client.collections.get(ttl_col_name)
    primary_col = client.collections.get(col_name)

    while True:
        elapsed = time.time() - last_execution

        tenants = primary_col.tenants.get()
        tenants_names = [
            name
            for name, tenant in tenants.items()
            if tenant.activity_status == weaviate.schema.TenantActivityStatus.FROZEN
        ]

        tenants_to_enable = get_random_tenants(
            tenants_names, len(tenants), percentage_of_tenants
        )
        if any(tenants_to_enable):
            logger.info(f"Enabling {len(tenants_to_enable)} tenants")
            for tenant in tenants_to_enable:
                primary_col.tenants.update(
                    tenants=[
                        Tenant(
                            name=tenant,
                            activate_status=weaviate.schema.TenantActivityStatus.HOT,
                        )
                    ]
                )
                update_data_batch(primary_col, tenant)
                update_ttl_for_tenant(ttl_col, tenant)


def get_random_tenants(tenants_names, total_tenants, percentage):
    if len(tenants_names) == 0 or total_tenants == 0:
        return []
    num_tenants = min(int(total_tenants * (percentage / 100)), len(tenants_names))
    random_tenants = random.sample(tenants_names, num_tenants)
    return random_tenants


def update_data_batch(col_t, tenant):

    # Create a list of all possible objects IDs
    all_objects = list(range(objects_per_tenant))

    # Randomly select a subset of objects
    subset = random.sample(all_objects, objects_to_update)
    with col_t.with_tenant(tenant).batch.dynamic() as batch:
        for i in subset:
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


def update_ttl_for_tenant(ttl_col: weaviate.collections.Collection, tenant_name: str):
    expiration = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=ttl
    )

    response = ttl_col.query.fetch_objects(
        filters=Filter.by_property("tenant_name").equal(tenant_name), limit=1
    )

    if any(response.objects):
        ttl_col.data.update(
            uuid=response.objects[0].uuid,
            properties={
                "expiration": expiration.isoformat(),
            },
        )


user_enabling_loop()
client.close()
