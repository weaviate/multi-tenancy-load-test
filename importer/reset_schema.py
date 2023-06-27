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
client = weaviate.Client(f"http://{host}", timeout_config=(20, 240))


def reset_schema(client: weaviate.Client):
    client.schema.delete_all()
    class_payload = {
        "class": "MultiTenancyTest",
        "description": "A class to test multi-tenancy with many props",
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
            "tenantKey": "tenant_id",
        },
    }
    res = requests.post(f"http://{host}/v1/schema", json=class_payload)
    print(res.status_code)


reset_schema(client)
