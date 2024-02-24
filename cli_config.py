import subprocess
import os


def get_git_short_hash():
    try:
        # Run the git command to get the short hash of the current commit
        short_hash = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.STDOUT
            )
            .decode()
            .strip()
        )
        return short_hash
    except subprocess.CalledProcessError as e:
        # Handle errors from the subprocess, such as if the directory is not a Git repository
        raise RuntimeError(
            "Error: This script is not running in a Git repository or there was an issue with Git command execution."
        ) from e
    except FileNotFoundError:
        # Handle errors if git is not installed
        raise RuntimeError(
            "Error: Git is not installed or not found in the PATH."
        ) from None
    except Exception as e:
        # Handle unexpected errors
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


def init_config() -> (Config, dict):
    cfg = Config()
    cfg.namespace = "weaviate"
    cfg.project = "semi-automated-benchmarking"
    cfg.region = "us-central1"
    cfg.zone = "us-central1-c"
    cfg.cluster_name = "mt-load-test"
    cfg.path_to_secret_file = (
        "/Users/etiennedilocker/Downloads/semi-automated-benchmarking-d48b1be49cd1.json"
    )
    cfg.git_hash = get_git_short_hash()

    env = os.environ.copy()

    env["TF_VAR_cluster_name"] = cfg.cluster_name
    env["TF_VAR_project"] = cfg.project
    env["TF_VAR_region"] = cfg.region
    env["TF_VAR_zone"] = cfg.zone
    env["K8S_NAMESPACE"] = cfg.namespace
    env["GIT_HASH"] = cfg.git_hash
    return cfg, env
