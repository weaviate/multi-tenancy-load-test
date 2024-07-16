import weaviate
import weaviate.classes as wvc
from weaviate.collections.classes.tenants import TenantActivityStatus, Tenant
import time
import random
import sys
import numpy as np
import uuid
import os
import requests
import string
from loguru import logger
from typing import Optional
from prometheus_client import start_http_server, Counter, Summary


host = os.getenv("HOST")
host_grpc = os.getenv("HOST_GRPC")

client = weaviate.connect_to_custom(
    http_host=host,
    http_port=80,
    http_secure=False,
    grpc_host=host_grpc,
    grpc_port=50051,
    grpc_secure=False,
)

total_tenants = int(os.getenv("TOTAL_TENANTS"))
tenants_per_cycle = int(os.getenv("TENANTS_PER_CYCLE"))
prometheus_port = int(os.getenv("PROMETHEUS_PORT") or 8000)



def do(client: weaviate.WeaviateClient):
    start_http_server(prometheus_port)

    tenants_onloaded = Counter("tenants_onloaded", "Number of tenants onloaded.")
    tenants_onloaded_seconds = Summary("tenant_onloaded_seconds", "Duration it took to onload tenants")

    col = client.collections.get("MultiTenancyTest")

    before = time.time()
    
    i = 0
    while i < total_tenants:
        try: 
            tenants = [ tenant.name for tenant in col.tenants.get().values() if tenant.activity_status in [TenantActivityStatus.OFFLOADED]][:tenants_per_cycle]
        except Exception as e:
            tenants = []
            logger.info(f"Error getting tenants: {e}. Retrying..")
        if tenants:
            for attempt in range(100):
                try:    
                    col.tenants.update(
                                tenants=[
                                    Tenant(
                                        name=tenant,
                                        activity_status=TenantActivityStatus.ACTIVE,
                                    ) for tenant in tenants
                                ])
                    break
                except Exception as e:
                    logger.error(e)
                    sleep = random.randrange(0,5000)
                    logger.info(f"sleep {sleep}ms, then retry {attempt}")
                    time.sleep(sleep/1000)
                
                logger.info(f"onloading {len(tenants)} tenants")
            tenants_onloaded.inc(len(tenants))
            
            timeout = 600  # 10 minutes
            start_time = time.time()
            while True:
                try:
                    tenants_updated = [tenant.name for tenant in col.tenants.get_by_names(tenants).values() if tenant.activity_status == TenantActivityStatus.ACTIVE]
                except Exception as e:
                    logger.info(f"Error getting tenants: {e}. Retrying..")
                if len(tenants_updated) == len(tenants) or time.time() - start_time >= timeout:
                    break
                time.sleep(1)
            i += len(tenants)
        else:
            logger.warning(f"No tenants found to ONLOAD. Onloaded {i} tenants so far, retrying...")
            try:
                tenants_current = [ tenant.name for tenant in col.tenants.get().values() if tenant.activity_status in [TenantActivityStatus.ACTIVE]]
                if len(tenants_current) == total_tenants:
                    logger.info(f"All tenants are already onloaded")
                    break
            except Exception as e:
                    logger.info(f"Error getting tenants: {e}. Retrying..")
            
    took = time.time() - before
    tenants_onloaded_seconds.observe(took)
    
    logger.info(
            f"onloading {len(tenants)} tenants took {took}s"
        )
    tenants_updated = [tenant for tenant in col.tenants.get().values() if tenant.activity_status == TenantActivityStatus.ACTIVE]
    if len(tenants_updated) < len(tenants):
        logger.warning(f"Not all tenants have been onloaded, {len(tenants_updated)} out of {len(tenants)}")

do(client)