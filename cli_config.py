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
    zone: str
    namespace: str
    project: str
    cluster_name: str

    # will be determined as part of the run
    weaviate_hostname: str
    grafana_hostname: str
    grafana_password: str
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
        print(f"created a new cluster name: {cfg.cluster_name}")
    else:
        cfg.cluster_name = cluster_name

    env = os.environ.copy()

    env["TF_VAR_cluster_name"] = cfg.cluster_name
    env["TF_VAR_project"] = cfg.project
    env["TF_VAR_region"] = cfg.region
    env["TF_VAR_zone"] = cfg.zone
    env["K8S_NAMESPACE"] = cfg.namespace
    env["GIT_HASH"] = cfg.git_hash
    return cfg, env
