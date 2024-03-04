import weaviate
import weaviate.classes as wvc
import time
import datetime


def client(host: str, grpc_host: str) -> weaviate.WeaviateClient:
    return weaviate.connect_to_custom(
        http_host=host,
        http_port=80,
        grpc_host=grpc_host,
        grpc_port=50051,
        http_secure=False,
        grpc_secure=False,
    )


def create_backup(client: weaviate.WeaviateClient, backup_id: str):
    client.backup.create(
        backup_id,
        weaviate.backup.BackupStorage.GCS,
    )


def wait_for_backup_complete(
    client: weaviate.WeaviateClient, backup_id: str, interval=30, max_wait=3600
):
    start = time.time()
    while True:
        now = time.time()
        elapsed_delta = datetime.timedelta(seconds=now - start)
        if now - start > max_wait:
            raise Exception("backup timed out in {elapsed_delta}")

        status = client.backup.get_create_status(
            backup_id,
            weaviate.backup.BackupStorage.GCS,
        )
        if status.status == weaviate.backup.backup.BackupStatus.SUCCESS:
            print(f"Backup finished successfully in {elapsed_delta}")
            return
        elif status.status == weaviate.backup.backup.BackupStatus.FAILED:
            raise Exception(f"backup {backup_id} failed: {status}")
        elif status.status == weaviate.backup.backup.BackupStatus.STARTED:
            print(f"Backup still running. Time elapsed: {elapsed_delta}")
        else:
            raise Exception(f"unrecoginzed backup status: {status.status}")

        time.sleep(interval)


def restore_backup(client: weaviate.WeaviateClient, backup_id: str):
    client.backup.restore(
        backup_id,
        weaviate.backup.BackupStorage.GCS,
    )


def wait_for_backup_restore_complete(
    client: weaviate.WeaviateClient, backup_id: str, interval=30, max_wait=3600
):
    start = time.time()
    while True:
        now = time.time()
        elapsed_delta = datetime.timedelta(seconds=now - start)
        if now - start > max_wait:
            raise Exception("backup restore timed out in {elapsed_delta}")

        status = client.backup.get_restore_status(
            backup_id,
            weaviate.backup.BackupStorage.GCS,
        )
        if status.status == weaviate.backup.backup.BackupStatus.SUCCESS:
            print(f"Backup restore finished successfully in {elapsed_delta}")
            return
        elif status.status == weaviate.backup.backup.BackupStatus.FAILED:
            raise Exception(f"backup {backup_id} failed: {status}")
        elif status.status == weaviate.backup.backup.BackupStatus.STARTED:
            print(f"Backup restore still running. Time elapsed: {elapsed_delta}")
        else:
            raise Exception(f"unrecoginzed backup status: {status.status}")

        time.sleep(interval)
