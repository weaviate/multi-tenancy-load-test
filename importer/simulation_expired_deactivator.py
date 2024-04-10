import os
import weaviate
import weaviate.classes as wvc
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
prometheus_port = int(os.getenv("PROMETHEUS_PORT") or 8000)

client = weaviate.connect_to_custom(
    http_host=host,
    http_port=port,
    http_secure=False,
    grpc_host=host_grpc,
    grpc_port=port_grpc,
    grpc_secure=False,
)

last_execution = time.time()


def deactivate_loop():
    global last_execution
    ttl_col = client.collections.get(ttl_col_name)

    while True:
        elapsed = time.time() - last_execution
        if elapsed < tick_interval:
            time.sleep(tick_interval - elapsed)

        logger.info("start new cycle")

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        res = ttl_col.query.fetch_objects(
            limit=1000,
            filters=wvc.query.Filter.by_property("expiration").less_or_equal(now),
        )

        print(len(res.objects))

        last_execution = time.time()


deactivate_loop()
