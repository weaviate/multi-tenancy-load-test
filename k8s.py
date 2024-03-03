import time
from datetime import datetime, timedelta
from kubernetes import client, utils
import yaml


def get_job_completion_status(job_name: str, namespace: str) -> tuple:
    """
    Checks the completion status of a specified job in a given namespace.

    Parameters:
    - job_name: The name of the Kubernetes job.
    - namespace: The Kubernetes namespace where the job is located.

    Returns:
    A tuple (bool, int, int) with the meaning:
    - A boolean indicating if the job is complete (True if complete, False otherwise)
    - The current number of completions
    - The desired number of completions
    """

    try:
        v1 = client.BatchV1Api()

        # Fetch the job details
        job = v1.read_namespaced_job(name=job_name, namespace=namespace)

        # Desired completions
        desired_completions = (
            job.spec.completions if job.spec.completions is not None else 0
        )

        # Current completions
        current_completions = (
            job.status.succeeded if job.status.succeeded is not None else 0
        )

        # Determine completion status
        is_complete = current_completions >= desired_completions

        return (is_complete, current_completions, desired_completions)

    except client.exceptions.ApiException as e:
        print(f"An API error occurred: {e}")
        return (False, 0, 0)

    except Exception as e:
        print(f"An error occurred: {e}")
        return (False, 0, 0)


def wait_for_job_completion(
    job_name: str,
    namespace: str,
    check_interval=10,
    callback=None,
    max_wait_time=None,
):
    """
    Waits for a specified job to complete, checking its status at specified intervals.

    Parameters:
    - job_name: The name of the Kubernetes job.
    - namespace: The Kubernetes namespace where the job is located.
    - check_interval: How often (in seconds) to check the job's status.
    - callback: An optional callback function that is called with the current job status
                on each wait cycle. The callback should accept three arguments:
                current_completions, desired_completions, and elapsed_time.
    - max_wait_time: The maximum time to wait for the job to complete, in seconds.
                     If None, waits indefinitely.

    Raises:
    - TimeoutError: If the job does not complete within the maximum wait time.

    Prints the current number of completions and the time elapsed if the job is not complete yet.
    """

    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=max_wait_time) if max_wait_time else None

    while True:
        (
            is_complete,
            current_completions,
            desired_completions,
        ) = get_job_completion_status(job_name, namespace)

        if is_complete:
            print(
                f"Job '{job_name}' completed. {current_completions}/{desired_completions} completions."
            )
            break
        else:
            now = datetime.now()
            if end_time and now >= end_time:
                raise TimeoutError(
                    f"Job '{job_name}' did not complete within {max_wait_time} seconds."
                )

            elapsed_time = now - start_time
            print(
                f"Waiting for job '{job_name}' to complete. Current completions: {current_completions}/{desired_completions}. Time elapsed: {elapsed_time}"
            )

            if callback:
                callback(current_completions, desired_completions, elapsed_time)

            time.sleep(check_interval)


def check_statefulset_pods_ready_and_count(
    statefulset_name: str, total_desired_pods: int, namespace: str
) -> (int, int):
    """
    Checks the number of ready pods in a specified StatefulSet and returns this number along with the total desired count of pods.

    Args:
    - statefulset_name (str): The name of the StatefulSet to check.
    - namespace (str): The namespace in which the StatefulSet resides.

    Returns:
    - A tuple of two integers:
        - The first integer represents the number of pods that are currently in a ready state.
        - The second integer represents the total number of pods desired according to the StatefulSet's specification.
    """
    try:
        v1 = client.CoreV1Api()

        # Count ready pods
        ready_pods = 0
        label_selector = f"app.kubernetes.io/name=={statefulset_name}"
        pods = v1.list_namespaced_pod(namespace, label_selector=label_selector)
        for pod in pods.items:
            if pod.status.phase == "Running" and all(
                [cs.ready for cs in pod.status.container_statuses]
            ):
                ready_pods += 1

        return ready_pods, total_desired_pods
    except Exception as e:
        print(f"error retrieving status from k8s api: {e}")
        return 0, total_desired_pods


def wait_for_statefulset_pods_ready_with_display(
    statefulset_name: str,
    total_desired_pods: int,
    namespace: str,
    check_interval=10,
    max_wait_time=None,
):
    """
    Waits for all pods in a specified StatefulSet to be ready, displaying the number of ready pods during each wait interval.

    Args:
    - statefulset_name (str): The name of the StatefulSet to monitor.
    - total_desired_pods (int): How many pods should we wait for?
    - namespace (str): The namespace where the StatefulSet is deployed.
    - check_interval (int): How often (in seconds) to check the StatefulSet's readiness status.
    - max_wait_time (int, optional): The maximum amount of time (in seconds) to wait for the StatefulSet to become ready. If None, will wait indefinitely.

    Raises:
    - TimeoutError: If the StatefulSet does not become ready within the specified `max_wait_time`.

    Note:
    This function prints updates to the console regarding the readiness status of the StatefulSet's pods, including how many are ready out of the total desired.
    """
    # Initialize the CoreV1Api client
    v1 = client.CoreV1Api()

    start_time = datetime.now()
    end_time = start_time + timedelta(seconds=max_wait_time) if max_wait_time else None

    while True:
        ready_pods, total_desired_pods = check_statefulset_pods_ready_and_count(
            statefulset_name, total_desired_pods, namespace
        )
        if ready_pods == total_desired_pods:
            print(
                f"All {total_desired_pods} pods in StatefulSet '{statefulset_name}' are ready."
            )
            break

        now = datetime.now()
        if end_time and now >= end_time:
            raise TimeoutError(
                f"Not all pods in StatefulSet '{statefulset_name}' were ready within {max_wait_time} seconds."
            )

        elapsed_time = now - start_time
        print(
            f"Waiting for all pods in StatefulSet '{statefulset_name}' to be ready. {ready_pods}/{total_desired_pods} pods are ready. Time elapsed: {elapsed_time}"
        )
        time.sleep(check_interval)


def get_external_ip_by_app_name(app_name: str):
    try:
        v1 = client.CoreV1Api()
        services = v1.list_service_for_all_namespaces(
            label_selector=f"app.kubernetes.io/name={app_name}"
        )

        for svc in services.items:
            if (
                svc.status.load_balancer.ingress
                and len(svc.status.load_balancer.ingress) > 0
            ):
                external_ip = svc.status.load_balancer.ingress[0].ip
                return external_ip
    except Exception as e:
        print(f"error retrieving status from k8s api: {e}")

    # If no service is found or if no external IP is available, return None or handle as needed.
    return None


def get_external_ip(svc_name: str):
    v1 = client.CoreV1Api()
    # List all services in all namespaces without using a label selector
    services = v1.list_service_for_all_namespaces()

    for svc in services.items:
        # Check if the service name matches the requested service name
        if svc.metadata.name == svc_name:
            # Check if the service has an external IP address
            if (
                svc.status.load_balancer.ingress
                and len(svc.status.load_balancer.ingress) > 0
            ):
                external_ip = svc.status.load_balancer.ingress[0].ip
                return external_ip

    # If no matching service is found or if no external IP is available, return None or handle as needed.
    return None


def replace_variables_in_yaml(file_path, variables):
    """
    Reads a YAML file and replaces variables in it.

    :param file_path: Path to the YAML file.
    :param variables: Dictionary of variable names and their values.
    :return: The YAML content as a string with variables substituted.
    """
    with open(file_path, "r") as file:
        content = file.read()
        for key, value in variables.items():
            content = content.replace(f"${{{key}}}", value)
    return content


def apply_yaml(yaml_file_path: str, namespace: str, env: dict):
    yaml_content_with_variables_replaced = replace_variables_in_yaml(
        yaml_file_path, env
    )
    yaml_object = yaml.safe_load(yaml_content_with_variables_replaced)
    utils.create_from_dict(client.ApiClient(), yaml_object, namespace=namespace)


from typing import Any
from kubernetes import client, config


def scale_deployment(deployment_name: str, namespace: str, num_replicas: int) -> Any:
    """
    Scale a Kubernetes deployment to the specified number of replicas.

    Parameters:
    - deployment_name (str): The name of the deployment to scale.
    - namespace (str): The namespace where the deployment is located.
    - num_replicas (int): The desired number of replicas.

    Returns:
    - Any: The API response from Kubernetes. Typically, this is a V1DeploymentScale object.

    This function requires the Kubernetes cluster to be accessible and
    the current context set to the appropriate cluster if using outside
    of a cluster environment.
    """

    api_instance = client.AppsV1Api()
    body = {"spec": {"replicas": num_replicas}}

    try:
        api_response = api_instance.patch_namespaced_deployment_scale(
            name=deployment_name, namespace=namespace, body=body
        )
        print(f"Deployment {deployment_name} scaled to {num_replicas} replicas.")
        return api_response
    except client.ApiException as e:
        print(
            f"Exception when calling AppsV1Api->patch_namespaced_deployment_scale: {e}"
        )
        return None
    except Exception as e:
        print(
            f"Exception when calling AppsV1Api->patch_namespaced_deployment_scale: {e}"
        )
        return None
