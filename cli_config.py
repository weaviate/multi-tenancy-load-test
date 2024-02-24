import subprocess
import os
import click


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


def init_config(
    zone, region, namespace, project, cluster_name, path_to_secret_file
) -> (Config, dict):
    cfg = Config()
    cfg.namespace = namespace
    cfg.project = project
    cfg.region = region
    cfg.zone = zone
    cfg.cluster_name = cluster_name
    cfg.path_to_secret_file = path_to_secret_file
    cfg.git_hash = get_git_short_hash()

    env = os.environ.copy()

    env["TF_VAR_cluster_name"] = cfg.cluster_name
    env["TF_VAR_project"] = cfg.project
    env["TF_VAR_region"] = cfg.region
    env["TF_VAR_zone"] = cfg.zone
    env["K8S_NAMESPACE"] = cfg.namespace
    env["GIT_HASH"] = cfg.git_hash
    return cfg, env
