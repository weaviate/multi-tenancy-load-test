import subprocess
import json
import base64
import time
import os
from kubernetes import client, config, utils
import click
import questionary
import k8s
from rich.console import Console
from rich.markdown import Markdown
import sys

# TODO: config management:


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

console = Console()


def create_cluster():
    console.print(Markdown("## Create GKE cluster"))
    subprocess.run(["terraform", "init"], cwd="terraform", env=env)
    subprocess.run(["terraform", "apply", "--auto-approve"], cwd="terraform", env=env)
    setup_kubernetes_cluster(cfg.cluster_name, cfg.zone, cfg.project, cfg.namespace)


def run_command(command):
    output = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
    print("Command output:", output.decode())


def setup_kubernetes_cluster(cluster_name, zone, project, k8s_namespace):
    # gcloud command to get credentials
    gcloud_command = f'gcloud container clusters get-credentials "{cluster_name}" --zone "{zone}" --project {project}'
    run_command(gcloud_command)

    # kubectl command to create namespace
    kubectl_create_ns = f'kubectl create ns "{k8s_namespace}"'
    run_command(kubectl_create_ns)

    # kubectl command to set context
    kubectl_set_context = f"kubectl config set-context $(kubectl config current-context) --namespace {k8s_namespace}"
    run_command(kubectl_set_context)
    kubectl_create_secret = f"kubectl create secret generic backup-secret --from-file=GOOGLE_APPLICATION_CREDENTIALS={cfg.path_to_secret_file}"


def deploy_weaviate():
    console.print(Markdown("## Deploy Weaviate onto cluster"))
    subprocess.run(["weaviate/deploy.sh"], shell=True)


def deploy_observability():
    console.print(Markdown("## Deploy Observability Stack"))
    subprocess.run(["prometheus/deploy.sh"], shell=True)
    cfg.grafana_hostname, cfg.grafana_password = grafana_credentials()


def grafana_credentials():
    external_ip = k8s.get_external_ip("grafana")
    while external_ip == "pending" or not external_ip:
        print("External IP is still pending. Retrying in 5 seconds...", file=sys.stderr)
        time.sleep(5)
        external_ip = get_external_ip()

    password_b64 = subprocess.run(
        [
            "kubectl",
            "get",
            "secret",
            "observability-grafana",
            "-o",
            "jsonpath={.data.admin-password}",
        ],
        capture_output=True,
        text=True,
    )
    password = base64.b64decode(password_b64.stdout).decode("utf-8")

    print("Grafana")
    print("=======")
    print(f"Host: http://{external_ip}")
    print("Username: admin")
    print(f"Password: {password}")

    return (external_ip, password)


def wait_weaviate_ready():
    console.print(Markdown("## Wait for Weaviate pods"))
    k8s.wait_for_statefulset_pods_ready_with_display(
        "weaviate", "weaviate", 10, 15 * 60
    )
    cfg.weaviate_hostname = weaviate_hostname()


def weaviate_hostname() -> str:
    external_ip = k8s.get_external_ip("grafana")
    while external_ip == "pending" or not external_ip:
        print("External IP is still pending. Retrying in 5 seconds...", file=sys.stderr)
        time.sleep(5)
        external_ip = get_external_ip()


def push_images():
    console.print(
        Markdown("## Build and push docker images for importing and querying")
    )
    subprocess.run(["importer/build_and_push.sh"], shell=True)


def reset_schema():
    console.print(Markdown("## Reset Schema"))
    batch_v1 = client.BatchV1Api()
    job_name = "schema-resetter"
    jobs = batch_v1.list_namespaced_job(cfg.namespace)
    for job in jobs.items:
        if job.metadata.name == job_name:
            # Delete the job
            batch_v1.delete_namespaced_job(
                job_name, cfg.namespace, propagation_policy="Foreground"
            )
            print(f"Job '{job_name}' deleted.")
            break

    yaml_file_path = "importer/manifests/reset-schema-job.yaml"
    k8s.apply_yaml(yaml_file_path, cfg.namespace, env)
    print(f"YAML from '{yaml_file_path}' applied.")
    k8s.wait_for_job_completion(job_name, cfg.namespace, 5, max_wait_time=180)


def import_data():
    console.print(Markdown("## Import Data"))
    console.print(Markdown("### Warning: This will likely take a long time!"))
    subprocess.run(["importer/import.sh"], shell=True)
    k8s.wait_for_job_completion("importer", "weaviate", 60, max_wait_time=3 * 60 * 60)


def run_all_steps():
    create_cluster()
    deploy_weaviate()
    deploy_observability()
    wait_weaviate_ready()
    push_images()
    reset_schema()
    import_data()


@click.command()
@click.option("--interactive", is_flag=True, help="Run in interactive mode.")
def main(interactive):
    # Load k8s config
    config.load_kube_config()

    if interactive:
        console.print(Markdown("# Multi-Tenancy Load Test - INTERACTIVE MODE"))
        run_all = questionary.confirm("Would you like to run all steps?").ask()
        if run_all:
            run_all_steps()
        else:
            actions = {
                "Create cluster": create_cluster,
                "Deploy Weaviate": deploy_weaviate,
                "Deploy observability": deploy_observability,
                "Wait for Weaviate to be ready": wait_weaviate_ready,
                "Push images": push_images,
                "Reset schema": reset_schema,
                "Import data": import_data,
            }

            choices = [{"name": action} for action in actions]

            selected_steps = questionary.checkbox(
                "Select steps to execute (space to select, enter to confirm):",
                choices=choices,
            ).ask()

            # Execute selected steps
            if selected_steps:
                for step in selected_steps:
                    actions[step]()
            else:
                print("No steps selected. Exiting.")
    else:
        console.print(Markdown("# Multi-Tenancy Load Test"))
        run_all_steps()


if __name__ == "__main__":
    main()
