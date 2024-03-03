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
import weaviate_interaction
import warnings
import prometheus

warnings.filterwarnings("ignore", category=ResourceWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)


cfg, env = None, None
console = Console()


def create_cluster():
    console.print(Markdown(f"## Create GKE cluster ({cfg.cluster_name})"))
    subprocess.run(["terraform", "init"], cwd="terraform", env=env, check=True)
    subprocess.run(
        ["terraform", "apply", "--auto-approve"], cwd="terraform", env=env, check=True
    )
    setup_kubernetes_cluster(cfg.cluster_name, cfg.zone, cfg.project, cfg.namespace)


def destroy_cluster():
    console.print(Markdown(f"## Destroy GKE cluster ({cfg.cluster_name})"))
    subprocess.run(
        ["terraform", "destroy", "--auto-approve"], cwd="terraform", env=env, check=True
    )


def run_command(command):
    output = subprocess.check_output(
        command,
        shell=True,
        stderr=subprocess.STDOUT,
    )
    print("Command output:", output.decode())


def setup_kubernetes_cluster(cluster_name, zone, project, k8s_namespace):
    # gcloud command to get credentials
    gcloud_command = f'gcloud container clusters get-credentials "{cluster_name}" --zone "{zone}" --project {project}'
    run_command(gcloud_command)

    # kubectl command to create namespace
    kubectl_create_ns = f'kubectl create ns "{k8s_namespace}" || true'
    run_command(kubectl_create_ns)

    # kubectl command to set context
    kubectl_set_context = f"kubectl config set-context $(kubectl config current-context) --namespace {k8s_namespace}"
    run_command(kubectl_set_context)

    kubectl_create_secret = f"kubectl create secret generic backup-secret --from-file=GOOGLE_APPLICATION_CREDENTIALS={cfg.path_to_secret_file}"
    try:
        run_command(kubectl_create_secret)
    except Exception as e:
        print(
            f"silently ignoring create secret error, this may fail on duplicate creation: {e}"
        )

    config.load_kube_config()


def deploy_weaviate():
    console.print(Markdown("## Deploy Weaviate onto cluster"))
    subprocess.run(["weaviate/deploy.sh"], shell=True, env=env, check=True)


def deploy_observability():
    console.print(Markdown("## Deploy Observability Stack"))
    subprocess.run(["prometheus/deploy.sh"], shell=True, env=env, check=True)
    cfg.grafana_hostname, cfg.grafana_password = grafana_credentials()


def grafana_credentials() -> (str, str):
    external_ip = k8s.get_external_ip_by_app_name("grafana")
    while external_ip == "pending" or not external_ip:
        print(
            "External IP (grafana) is still pending. Retrying in 5 seconds...",
            file=sys.stderr,
        )
        time.sleep(5)
        external_ip = k8s.get_external_ip_by_app_name("grafana")

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
        check=True,
    )
    password = base64.b64decode(password_b64.stdout).decode("utf-8")

    print("Grafana")
    print("=======")
    print(f"Host: http://{external_ip}")
    print("Username: admin")
    print(f"Password: {password}")

    return (external_ip, password)


def prometheus_host() -> str:
    external_ip = k8s.get_external_ip_by_app_name("prometheus")
    while external_ip == "pending" or not external_ip:
        print(
            "External IP (prometheus) is still pending. Retrying in 5 seconds...",
            file=sys.stderr,
        )
        time.sleep(5)
        external_ip = k8s.get_external_ip_by_app_name("prometheus")
    return external_ip


def wait_weaviate_ready():
    console.print(Markdown("## Wait for Weaviate pods"))
    k8s.wait_for_statefulset_pods_ready_with_display(
        "weaviate", cfg.weaviate_pods, "weaviate", 10, 15 * 60
    )
    cfg.weaviate_hostname, cfg.weaviate_grpc_hostname = weaviate_hostname()


def weaviate_hostname() -> (str, str):
    http_host = k8s.get_external_ip("weaviate")
    while http_host == "pending" or not http_host:
        print(
            "External IP (http) is still pending. Retrying in 5 seconds...",
            file=sys.stderr,
        )
        time.sleep(5)
        http_host = k8s.get_external_ip("weaviate")

    grpc_host = k8s.get_external_ip("weaviate-grpc")
    while grpc_host == "pending" or not grpc_host:
        print(
            "External IP (grpc) is still pending. Retrying in 5 seconds...",
            file=sys.stderr,
        )
        time.sleep(5)
        grpc_host = k8s.get_external_ip("weaviate-grpc")

    return http_host, grpc_host


def push_images():
    console.print(
        Markdown("## Build and push docker images for importing and querying")
    )
    subprocess.run(["gcloud auth configure-docker"], shell=True, env=env, check=True)
    subprocess.run(["importer/build_and_push.sh"], shell=True, env=env, check=True)


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
    console.print(Markdown("## Start Import Data"))
    yaml_file_path = "importer/manifests/import-job.yaml"
    k8s.apply_yaml(yaml_file_path, cfg.namespace, env)
    print(f"YAML from '{yaml_file_path}' applied.")


def wait_for_import():
    if not cfg.weaviate_hostname:
        print("no weaviate hostname found, run wait_weaviate_ready step first")
        wait_weaviate_ready()

    console.print(Markdown("## Wait for import to finish"))
    console.print(Markdown("### Warning: This will likely take a long time!"))
    wclient = weaviate_interaction.client(
        cfg.weaviate_hostname, cfg.weaviate_grpc_hostname
    )

    def check_progress_fn(current: int, desired: int, elapsed_time: float):
        try:
            res = wclient.cluster.nodes(output="verbose")
            object_count = sum([node.stats.object_count for node in res])
            shard_count = sum([len(node.shards) for node in res])
            print(f"shards={shard_count} obects={object_count}")
        except Exception as e:
            print(f"could not get object count: {e}")

    k8s.wait_for_job_completion(
        "importer",
        "weaviate",
        60,
        callback=check_progress_fn,
        max_wait_time=3 * 60 * 60,
    )

    # print progress one more time
    check_progress_fn(0, 0, 0)


def query():
    console.print(Markdown("## Query"))
    cfg.prometheus_hostname = prometheus_host()

    query_pods = cfg.query_min_pods
    yaml_file_path = "importer/manifests/querying-deployment.yaml"
    env["QUERY_REPLICAS"] = str(query_pods)
    try:
        k8s.apply_yaml(yaml_file_path, cfg.namespace, env)
    except:
        # accept silent failure in case it exists already.
        pass
    print(f"YAML from '{yaml_file_path}' applied.")
    while query_pods <= cfg.query_max_pods:
        tenants = cfg.query_tenants_per_pod * query_pods
        users = cfg.query_users_per_tenant * tenants
        console.print(
            Markdown(f"### pods={query_pods} tenants={tenants} users={users}")
        )
        k8s.scale_deployment("query-deployment", cfg.namespace, query_pods)

        time.sleep(60)
        query = "sum(rate(vector_query_seconds_count[30s]))"
        qps = int(prometheus.query(f"http://{cfg.prometheus_hostname}", query, 30))
        query = "sum(rate(vector_query_seconds_sum[30s]))/sum(rate(vector_query_seconds_count[30s]))"
        mean_latency = (
            prometheus.query(f"http://{cfg.prometheus_hostname}", query, 30) * 1000
        )
        console.print(f"qps={qps} mean_latency={mean_latency:.2f}ms", style="bold")

        query_pods += 10

    # shut down querying
    query_pods = 0
    k8s.scale_deployment("query-deployment", cfg.namespace, query_pods)


def get_backup_id(cluster_name: str) -> str:
    # right now we can only do a single backup per run. Instead we could have a
    # persistent counter where restore always refers to the last created one,
    # but it is possible to create more than one by incrementing the counter or
    # so. For now a single backup per run should be fine.
    return f"{cfg.cluster_name}-backup"


def create_backup():
    if not cfg.weaviate_hostname:
        print("no weaviate hostname found, run wait_weaviate_ready step first")
        wait_weaviate_ready()

    console.print(Markdown("## Create a GCS backup"))
    wclient = weaviate_interaction.client(
        cfg.weaviate_hostname, cfg.weaviate_grpc_hostname
    )

    weaviate_interaction.create_backup(
        wclient,
        get_backup_id(cfg.cluster_name),
    )


def wait_for_backup():
    if not cfg.weaviate_hostname:
        print("no weaviate hostname found, run wait_weaviate_ready step first")
        wait_weaviate_ready()

    console.print(Markdown("## Wait for GCS backup to complete"))
    console.print(Markdown("### Warning: This will likely take a long time!"))

    wclient = weaviate_interaction.client(
        cfg.weaviate_hostname, cfg.weaviate_grpc_hostname
    )

    weaviate_interaction.wait_for_backup_complete(
        wclient,
        get_backup_id(cfg.cluster_name),
        interval=30,
        max_wait=60 * 60,
    )


def delete_collection():
    if not cfg.weaviate_hostname:
        print("no weaviate hostname found, run wait_weaviate_ready step first")
        wait_weaviate_ready()

    console.print(Markdown("## Delete Collections (in anticipation of backup restore)"))

    wclient = weaviate_interaction.client(
        cfg.weaviate_hostname, cfg.weaviate_grpc_hostname
    )

    max_attempts = 10
    for i in range(max_attempts):
        try:
            wclient.collections.delete_all()
            return
        except Exception as e:
            print(f"Delete failed, trying again: {e}")

    raise Exception(f"could not delete collection in {max_attempts}")


def restore_backup():
    if not cfg.weaviate_hostname:
        print("no weaviate hostname found, run wait_weaviate_ready step first")
        wait_weaviate_ready()

    console.print(Markdown("## Restore a GCS backup"))
    wclient = weaviate_interaction.client(
        cfg.weaviate_hostname, cfg.weaviate_grpc_hostname
    )

    weaviate_interaction.restore_backup(
        wclient,
        get_backup_id(cfg.cluster_name),
    )


def wait_for_backup_restore():
    if not cfg.weaviate_hostname:
        print("no weaviate hostname found, run wait_weaviate_ready step first")
        wait_weaviate_ready()

    console.print(Markdown("## Wait for GCS backup to restore"))
    console.print(Markdown("### Warning: This can take significant time!"))

    wclient = weaviate_interaction.client(
        cfg.weaviate_hostname, cfg.weaviate_grpc_hostname
    )

    weaviate_interaction.wait_for_backup_restore_complete(
        wclient,
        get_backup_id(cfg.cluster_name),
        interval=30,
        max_wait=60 * 60,
    )


@click.command()
@click.option("--zone", default="us-central1-c", help="Deployment zone.")
@click.option("--region", default="us-central1", help="Deployment region.")
@click.option("--namespace", default="weaviate", help="Kubernetes namespace.")
@click.option("--project", default="semi-automated-benchmarking", help="GCP project.")
@click.option(
    "--cluster-name", default="", help="Name of the Kubernetes cluster."
)  # default will be overriden from serialized state
@click.option("--step", default="", help="Execute a specific step")
def main(zone, region, namespace, project, cluster_name, step):
    global cfg
    global env

    cfg, env = init_config(
        zone,
        region,
        namespace,
        project,
        cluster_name,
    )

    try:
        config.load_kube_config()
    except Exception as e:
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
            "Wait for import to finish": wait_for_import,
            "Query": query,
            "Create Backup": create_backup,
            "Wait for Backup Creation": wait_for_backup,
            "Delete Collection (in anticipation of backup restore)": delete_collection,
            "Restore Backup": restore_backup,
            "Wait for Backup Restore": wait_for_backup_restore,
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
            "wait_for_import": wait_for_import,
            "query": query,
            "create_backup": create_backup,
            "wait_for_backup": wait_for_backup,
            "delete_collection": delete_collection,
            "restore_backup": restore_backup,
            "wait_for_backup_restore": wait_for_backup_restore,
            "destroy_cluster": destroy_cluster,
        }

        if step not in actions:
            print("Invalid step. Exiting.")
            sys.exit(1)

        actions[step]()


if __name__ == "__main__":
    main()
