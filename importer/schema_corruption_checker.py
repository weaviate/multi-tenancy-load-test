import weaviate
import time
import sys
import os
import requests
from loguru import logger

host = os.getenv("HOST")
tenants_goal = int(os.getenv("TENANTS_GOAL"))
client = weaviate.Client(f"http://{host}", timeout_config=(20, 240))

failure_threshold = 5
failures = 0


def check_schema_status(client: weaviate.Client):
    global failures
    res = requests.get(f"http://{host}/v1/schema/cluster-status")
    if res.status_code != 200:
        parsed = res.json()
        if "concurrent transaction" in parsed["error"]:
            logger.info("concurrent transaction, try again next time")
            return
        if failures < failure_threshold:
            logger.warning(res.json())
            failures += 1
        else:
            logger.error(res.json())
            sys.exit(1)
    else:
        failures = 0
        logger.info(res.json())


def check_progess(client: weaviate.Client):
    res = client.cluster.get_nodes_status()
    nodes = len(res)
    tenants = sum([n["stats"]["shardCount"] for n in res])
    objects = sum([n["stats"]["objectCount"] for n in res])
    logger.info(
        f"Progress on {nodes}-node cluster: tenants={tenants} objects={objects}"
    )
    if tenants >= tenants_goal:
        logger.info(f"reached tenant goal of {tenants} tenants")
        sys.exit(0)


i = 0
while True:
    if i % 10 == 0:
        check_progess(client)

    time.sleep(3)
    check_schema_status(client)

    i += 1
