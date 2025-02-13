import weaviate
import weaviate.classes as wvc
import os
from loguru import logger
from typing import Optional

host = os.getenv("HOST")
host_grpc = os.getenv("HOST_GRPC")
replication_factor = int(os.getenv("REPLICATION_FACTOR") or 1)


client = weaviate.connect_to_custom(
    http_host=host,
    http_port=80,
    http_secure=False,
    grpc_host=host_grpc,
    grpc_port=50051,
    grpc_secure=False,
)


def reset_schema(client: weaviate.WeaviateClient):
    client.collections.delete_all()
    client.collections.create(
        "MultiTenancyTest",
        vectorizer_config=None,
        multi_tenancy_config=wvc.config.Configure.multi_tenancy(enabled=True),
        replication_config=wvc.config.Configure.replication(factor=replication_factor, async_enabled=True, deletion_strategy=wvc.config.ReplicationDeletionStrategy.TIME_BASED_RESOLUTION),
        vector_index_config=wvc.config.Configure.VectorIndex.flat(
            quantizer=wvc.config.Configure.VectorIndex.Quantizer.bq()
        ),
    )


reset_schema(client)
