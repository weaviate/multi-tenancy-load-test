import weaviate
import time
import sys
import os
import requests
from loguru import logger

host = os.getenv("HOST")
tenants_goal = int(os.getenv("TENANTS_GOAL"))
client = weaviate.Client(f"http://{host}", timeout_config=(20, 240))


def check_progess(client: weaviate.Client):
    res = requests.get(f"http://{host}/v1/nodes?output=verbose")
    nodes = res.json().get("nodes")
    tenants = sum([n.get("stats").get("shardCount") for n in nodes])
    objects = sum([n.get("stats").get("objectCount") for n in nodes])
    logger.info(
        f"Progress on {len(nodes)}-node cluster: tenants={tenants} objects={objects}"
    )
    if tenants >= tenants_goal:
        logger.info(f"reached tenant goal of {tenants} tenants")
        sys.exit(0)


i = 0
while True:
    if i % 10 == 0:
        check_progess(client)
    i += 1
