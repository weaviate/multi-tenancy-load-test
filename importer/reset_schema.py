import weaviate
import time
import random
import sys
import uuid
import os
import requests
from loguru import logger
from typing import Optional

host = os.getenv("HOST")
replication_factor = int(os.getenv("REPLICATION_FACTOR") or 1)
client = weaviate.Client(f"http://{host}", timeout_config=(20, 240))


def reset_schema(client: weaviate.Client):
    client.schema.delete_all()
    class_payload = {
        "class": "MultiTenancyTest",
        "description": "A class to test multi-tenancy with many props",
        "vectorizer": "none",
        "replicationConfig": {
            "factor": replication_factor,
        },
        "properties": [
            {
                "dataType": ["text"],
                "tokenization": "field",
                "name": "tenant_id",
            },
            {"dataType": ["int"], "name": "int1"},
            {"dataType": ["int"], "name": "int2"},
            # {"dataType": ["int"], "name": "int3"},
            # {"dataType": ["int"], "name": "int4"},
            # {"dataType": ["int"], "name": "int5"},
            {"dataType": ["text"], "name": "text1"},
            {"dataType": ["text"], "name": "text2"},
            # {"dataType": ["text"], "name": "text3"},
            # {"dataType": ["text"], "name": "text4"},
            # {"dataType": ["text"], "name": "text5"},
            {"dataType": ["number"], "name": "number1"},
            {"dataType": ["number"], "name": "number2"},
            # {"dataType": ["number"], "name": "number3"},
            # {"dataType": ["number"], "name": "number4"},
            # {"dataType": ["number"], "name": "number5"},
        ],
        "multiTenancyConfig": {
            "enabled": True,
        },
    }
    res = requests.post(f"http://{host}/v1/schema", json=class_payload)
    print(res.status_code)
    if res.status_code > 299:
        print(res.json())
        sys.exit(1)


reset_schema(client)
