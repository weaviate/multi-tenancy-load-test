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
from cli_config import init_config


cfg, env = None, None
console = Console()


def create_cluster():
    console.print(Markdown(f"## Create GKE cluster ({cfg.cluster_name})"))
    subprocess.run(["terraform", "init"], cwd="terraform", env=env)
    subprocess.run(["terraform", "apply", "--auto-approve"], cwd="terraform", env=env)
    setup_kubernetes_cluster(cfg.cluster_name, cfg.zone, cfg.project, cfg.namespace)


def destroy_cluster():
    console.print(Markdown(f"## Destroy GKE cluster ({cfg.cluster_name})"))
    subprocess.run(["terraform", "destroy", "--auto-approve"], cwd="terraform", env=env)


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

    config.load_kube_config()


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
    subprocess.run(["importer/build_and_push.sh"], shell=True, env=env)


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
@click.option("--zone", default="us-central1-c", help="Deployment zone.")
@click.option("--region", default="us-central1", help="Deployment region.")
@click.option("--namespace", default="weaviate", help="Kubernetes namespace.")
@click.option("--project", default="semi-automated-benchmarking", help="GCP project.")
@click.option(
    "--cluster-name", default="", help="Name of the Kubernetes cluster."
)  # default will be overriden from serialized state
@click.option(
    "--path-to-secret-file",
    default="/Users/etiennedilocker/Downloads/semi-automated-benchmarking-d48b1be49cd1.json",
    help="Path to the GCP secret file that's used for backups.",
)  # TODO!
@click.option("--step", default="", help="Execute a specific step")
def main(zone, region, namespace, project, cluster_name, path_to_secret_file, step):
    global cfg
    global env

    cfg, env = init_config(
        zone,
        region,
        namespace,
        project,
        cluster_name,
        path_to_secret_file,
    )

    try:
        config.load_kube_config()
    except Excpetion as e:
        print(
            f"Can't load kubeconfig. This is fine if this is the first run of the script: {e}"
        )

    if step == "":
        console.print(Markdown("# Multi-Tenancy Load Test - INTERACTIVE MODE"))
        actions = {
            "Create cluster": create_cluster,
            "Deploy Weaviate": deploy_weaviate,
            "Deploy observability": deploy_observability,
            "Wait for Weaviate to be ready": wait_weaviate_ready,
            "Push images": push_images,
            "Reset schema": reset_schema,
            "Import data": import_data,
            "Destroy Cluster": destroy_cluster,
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
        actions = {
            "create_cluster": create_cluster,
            "deploy_weaviate": deploy_weaviate,
            "deploy_observability": deploy_observability,
            "wait_weaviate_ready": wait_weaviate_ready,
            "push_images": push_images,
            "reset_schema": reset_schema,
            "import_data": import_data,
            "destroy_cluster": destroy_cluster,
        }

        if step not in actions:
            print("Invalid step. Exiting.")
            sys.exit(1)

        actions[step]()


if __name__ == "__main__":
    main()
