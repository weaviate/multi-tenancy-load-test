import subprocess
import os
import click
import random
import string


def get_git_short_hash():
    try:
        short_hash = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.STDOUT
            )
            .decode()
            .strip()
        )
        return short_hash
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            "Error: This script is not running in a Git repository or there was an issue with Git command execution."
        ) from e
    except FileNotFoundError:
        raise RuntimeError(
            "Error: Git is not installed or not found in the PATH."
        ) from None
    except Exception as e:
        raise RuntimeError(f"Unexpected error: {str(e)}") from e


class Config:
    # set by the user

    # infra
    zone: str
    namespace: str
    project: str
    cluster_name: str
    weaviate_version: str
    weaviate_pods: int

    # importing
    replication_factor: int
    tenants_per_job: int
    objects_per_tenant: int
    parallel_importers: int
    importer_completions: int

    # querying
    query_tenants_per_pod: int
    query_users_per_tenant: int
    query_total_per_tenant: int
    query_frequency_per_minute: int
    query_min_pods: int
    query_max_pods: int

    # will be determined as part of the run
    weaviate_hostname: str = None
    weaviate_grpc_hostname: str = None
    grafana_hostname: str
    grafana_password: str
    prometheus_hostname: str
    git_hash: str


def get_cluster_name():
    # Check if .clustername exists in the current directory
    if os.path.exists(".clustername"):
        # Read the cluster name from the file
        with open(".clustername", "r") as file:
            cluster_name = file.read().strip()
    else:
        # Generate a new cluster name with 8 random letters or numbers
        random_string = "".join(
            random.choices(string.ascii_lowercase + string.digits, k=8)
        )
        cluster_name = f"mt-load-test-{random_string}"

        # Write the new cluster name to the file
        with open(".clustername", "w") as file:
            file.write(cluster_name)

    return cluster_name


def init_config(
    zone,
    region,
    namespace,
    project,
    cluster_name,
) -> (Config, dict):
    cfg = Config()
    cfg.namespace = namespace
    cfg.project = project
    cfg.region = region
    cfg.zone = zone
    cfg.path_to_secret_file = "./terraform/backup-service-account-key.json"
    cfg.git_hash = get_git_short_hash()
    if cluster_name == "":
        # the user didn't specify one, let's use our custom logic:
        cfg.cluster_name = get_cluster_name()
        print(f"using cluster name: {cfg.cluster_name}")
    else:
        cfg.cluster_name = cluster_name

    # todo: make configurable
    cfg.weaviate_pods = 12
    cfg.weaviate_version = "1.24.1"

    cfg.replication_factor = 1
    cfg.tenants_per_job = 1000
    cfg.objects_per_tenant = 1000
    cfg.vector_dimensions = 1536
    cfg.parallel_importers = 12
    cfg.importer_completions = 12

    cfg.query_tenants_per_pod = 10
    cfg.query_users_per_tenant = 5
    cfg.query_total_per_tenant = 1000000
    cfg.query_frequency_per_minute = 480
    cfg.query_min_pods = 10
    cfg.query_max_pods = 60

    # duplicate some config vars into the environment. This env is passed to
    # relevant commands that anticipate env substitution, such as yaml
    # manifests or terraform commands
    env = os.environ.copy()
    env["TF_VAR_cluster_name"] = cfg.cluster_name
    env["TF_VAR_project"] = cfg.project
    env["TF_VAR_region"] = cfg.region
    env["TF_VAR_zone"] = cfg.zone
    env["K8S_NAMESPACE"] = cfg.namespace
    env["GIT_HASH"] = cfg.git_hash
    env["WEAVIATE_VERSION"] = cfg.weaviate_version
    env["WEAVIATE_PODS"] = str(cfg.weaviate_pods)
    env["REPLICATION_FACTOR"] = str(cfg.replication_factor)
    env["TENANTS_PER_JOB"] = str(cfg.tenants_per_job)
    env["OBJECTS_PER_TENANT"] = str(cfg.objects_per_tenant)
    env["PARALLEL_IMPORTERS"] = str(cfg.parallel_importers)
    env["IMPORTER_COMPLETIONS"] = str(cfg.importer_completions)
    env["VECTOR_DIMENSIONS"] = str(cfg.vector_dimensions)
    env["QUERY_FREQUENCY_PER_MINUTE"] = str(cfg.query_frequency_per_minute)
    env["QUERY_TOTAL_PER_TENANT"] = str(cfg.query_total_per_tenant)
    env["QUERY_TENANTS_PER_POD"] = str(cfg.query_tenants_per_pod)
    env["QUERY_USERS_PER_TENANT"] = str(cfg.query_users_per_tenant)

    return cfg, env
