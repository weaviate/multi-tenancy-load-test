import weaviate
import weaviate.classes as wvc
import time
import random
import sys
import uuid
import os
import requests
from loguru import logger
from typing import Optional

host = os.getenv("HOST")
host_port = int(os.getenv("HOST_PORT") or 80)
host_grpc = os.getenv("HOST_GRPC")
grpc_port = int(os.getenv("GRPC_PORT") or 50051)
replication_factor = int(os.getenv("REPLICATION_FACTOR") or 1)

client = weaviate.connect_to_custom(
    http_host=host,
    http_port=host_port,
    http_secure=False,
    grpc_host=host_grpc,
    grpc_port=grpc_port,
    grpc_secure=False,
)


def reset_schema(client: weaviate.WeaviateClient):
    client.collections.delete_all()
    client.collections.create(
        "MultiTenancyTest",
        vectorizer_config=None,
        multi_tenancy_config=wvc.config.Configure.multi_tenancy(enabled=True),
        replication_config=wvc.config.Configure.replication(factor=replication_factor),
        vector_index_config=wvc.config.Configure.VectorIndex.flat(
            quantizer=wvc.config.Configure.VectorIndex.Quantizer.bq()
        ),
    )


reset_schema(client)
