import argparse
import json
import subprocess
import time
from contextlib import contextmanager
from typing import Iterator, TypedDict, Optional, Union, Iterable, Callable, io

with open("postgresql-ha/load.sql") as fp:
    POSTGRESQL_WORKLOAD_SQL = fp.read()

APPLICATIONS = {
    "postgresql-ha": {
        "chart": "bitnami/postgresql-ha",
        "version": "3.2.7",
        "namespace": "postgresql-ha",
        "values": "postgresql-ha/values.yaml",
        "repo_name": "bitnami",
        "repo_url": "https://charts.bitnami.com/bitnami",
        "workload": {
            "image": "bitnami/postgresql:11",
            "env": {
                "PGPASSWORD": "password",
                "PGCONNECT_TIMEOUT": "1",
            },
            "command": lambda host: [
                'psql',
                '-h', host,  # Set the host
                '-p', '5432',  # The port
                '-U', 'postgres',  # The user
                '-d', 'postgres',  # The database
                '-c', POSTGRESQL_WORKLOAD_SQL,  # The SQL to run
            ],
            "pod_filter": lambda pod_name: pod_name.startswith("postgresql-ha-pgpool-"),
        }
    },
    "redis-cluster": {
        "chart": "bitnami/redis-cluster",
        "version": "3.1.10",
        "namespace": "redis-cluster",
        "values": "redis-cluster/values.yaml",
        "repo_name": "bitnami",
        "repo_url": "https://charts.bitnami.com/bitnami",
    }
}


@contextmanager
def temporary_kubernetes_cluster(name: str = "temp", region: str = 'ams3') -> Iterator[str]:
    create = subprocess.run(['doctl', 'kubernetes', 'cluster', 'create', '--region', region, name])

    if create.returncode > 0:
        raise Exception("Failed creating Kubernetes cluster")

    yield {'contextName': f"do-{region}-{name}"}

    delete = subprocess.run(['doctl', 'kubernetes', 'cluster', 'delete', name, '-f'])

    if delete.returncode > 0:
        raise Exception("Failed deleting Kubernetes cluster")


Command = type(Union['test', 'deploy', 'destroy', 'all'])


class Arguments(TypedDict):
    cluster: Optional[str]
    command: Command
    application: str
    results_file: Optional[io.TextIO]


def parse_arguments() -> Arguments:
    parser = argparse.ArgumentParser()
    parser.add_argument('command', type=str, choices=['test', 'deploy', 'destroy', 'all'], default='all')
    parser.add_argument('application', type=str, choices=APPLICATIONS.keys(), help='The application under test.')
    parser.add_argument('--cluster', type=str,
                        help='The name of the cluster to use, if left empty a temporary cluster will be created.')
    parser.add_argument('--results-file', '-f', type=argparse.FileType('a'),
                        help='The file to write the results to. Only applicable if tests are ran.')
    args = parser.parse_args()

    return {
        'cluster': args.cluster,
        'command': args.command,
        'application': args.application,
        'results_file': args.results_file,
    }


def create_namespace(name: str):
    return subprocess.run(["kubectl", "create", "namespace", name])


def deploy(namespace: str, name: str, chart: str, values: str, version: str):
    return subprocess.run([
        "helm", "install", name, chart,
        "--values", values,
        "--namespace", namespace,
        "--version", version,
    ])


def destroy_deployment(namespace: str):
    return subprocess.run([
        "helm", "delete", "postgresql-ha", "--namespace", namespace
    ])


def destroy_namespace(namespace: str):
    return subprocess.run([
        "kubectl", "delete", "namespace", namespace
    ])


def get_pods_data(namespace: str) -> dict:
    query = subprocess.run([
        "kubectl", "get", "pods", "--output", "json", "--namespace", namespace,
    ], stdout=subprocess.PIPE, text=True)

    if query.returncode > 0:
        raise Exception(f"Failed retrieving pod data: {query.stderr}")

    return json.loads(query.stdout)


def get_container_statuses(namespace: str) -> Iterable:
    pods_data = get_pods_data(namespace=namespace)

    yield from (container_status
                for pod in pods_data["items"]
                for container_status in pod["status"].get("containerStatuses", [])
                )


def get_workload_pod_ips(filter_function: Callable[[str], bool], namespace: str) -> Iterable[Optional[str]]:
    pods_data = get_pods_data(namespace=namespace)

    filtered_pods = filter(
        lambda pod: filter_function(pod["metadata"]["name"]),
        pods_data["items"]
    )

    yield from map(lambda pod: pod["status"].get("podIP"), filtered_pods)


def run_test(namespace: str, workload) -> dict:
    def execute_workload_test(host: str):
        return subprocess.run([
            'kubectl', 'run', 'workload', '--rm', '--tty', '-i', '--restart', 'Never',
            '--namespace', "default", '--image', workload["image"],
            *[x for name, value in workload["env"].items() for x in ("--env", f"{name}={value}")],
            '--command', '--', *workload["command"](host),
        ])

    # Define a variable to hold the metrics we are collecting
    metrics: dict = {
        'start_time': time.time(),
        'time_to_initialize': None,
        'time_to_first_request': None,
        'time_to_all_requests': None,
    }

    def all_containers_initialized(namespace: str) -> bool:
        # Check if all containers are ready
        container_statuses = get_container_statuses(namespace=namespace)

        # Check if all containers initialized
        return all(map(lambda x: x["ready"], container_statuses))

    def can_handle_request(host: str) -> bool:
        # Run a small workload as to test if it is functional
        workload_result = execute_workload_test(host=host)

        # Inspect the status code to see if our workload test was successful
        return workload_result.returncode == 0

    def amount_of_restarts(namespace: str) -> int:
        return sum(container_status["restartCount"] for container_status in get_container_statuses(namespace))

    # Collect time based metrics until all are acquired
    while not all(metrics.values()):
        # Check if all containers are ready
        if not metrics["time_to_initialize"]:
            if all_containers_initialized(namespace=namespace):
                metrics["time_to_initialize"] = time.time() - metrics["start_time"]

        # Check if the application can process a workload
        if not metrics["time_to_first_request"] or not metrics["time_to_all_requests"]:
            workload_pods = get_workload_pod_ips(workload["pod_filter"], namespace=namespace)
            pods_can_handle_workload = [pod_name and can_handle_request(host=pod_name) and time.time()
                                        for pod_name in workload_pods]

            if not metrics["time_to_first_request"] and any(pods_can_handle_workload):
                # Find the time at which the first request succeeded
                first_request = min(filter(lambda x: not not x, pods_can_handle_workload))

                # Store the time till first request metric
                metrics["time_to_first_request"] = first_request - metrics["start_time"]

            if not metrics["time_to_all_requests"] \
                    and all(pods_can_handle_workload) \
                    and len(pods_can_handle_workload) > 0:
                metrics["time_to_all_requests"] = max(pods_can_handle_workload) - metrics["start_time"]

    # Set the amount of restarts metric
    metrics["restarts"] = amount_of_restarts(namespace)

    # Store the time start metric
    metrics["end_time"] = time.time()

    # Print the collected metrics
    print(metrics)

    return metrics


def has_repo(name: str) -> bool:
    # Query Helm for all available repos
    query = subprocess.run(["helm", "repo", "list", "-o", "json"], stdout=subprocess.PIPE, text=True)
    repos: list = json.loads(query.stdout)

    # Find the repo which name matches the one we are looking for
    match = [filter(lambda item: item["name"] == name, repos)]

    # Return true if we found a match
    return len(match) > 0


def add_repo(name: str, url: str):
    if not has_repo(name):
        result = subprocess.run(["helm", "repo", "add", name, url])

        if result.returncode > 0:
            raise Exception("Failed adding bitnami repo")


def store_metrics(metrics: dict, file: io.TextIO) -> None:
    # Encode the data as a JSON string
    encoded_data = json.dumps(metrics)

    # Append the data to a file
    file.write(f"{encoded_data}\n")


def run_command(command: Command, cluster_context: str, application: str, results_file: Optional[io.TextIO]):
    app_config = APPLICATIONS[application]

    if command == "deploy":
        # Prepare the environment
        add_repo(app_config["repo_name"], app_config["repo_url"])
        create_namespace(app_config["namespace"])

        # Run the deploy
        deploy(namespace=app_config["namespace"],
               name=application,
               chart=app_config["chart"],
               values=app_config["values"],
               version=app_config["version"],
               )
    elif command == "destroy":
        destroy_deployment(app_config["namespace"])
        destroy_namespace(app_config["namespace"])
    elif command == "test":
        metrics = run_test(app_config["namespace"], app_config["workload"])

        if results_file:
            store_metrics(metrics, results_file)
    elif command == "all":
        run_command("deploy", cluster_context, application, results_file)
        run_command("test", cluster_context, application, results_file)
        run_command("destroy", cluster_context, application, results_file)
    else:
        raise Exception(f"Command '{command}' not found")


if __name__ == "__main__":
    # Retrieve the arguments
    arguments = parse_arguments()

    # Skip creating a temporary cluster if one is specified to be used
    if arguments["cluster"]:
        # Switch context in case we are not yet on the one indicated
        context_switch = subprocess.run(["kubectx", arguments["cluster"]])

        if context_switch.returncode > 0:
            raise Exception("Failed switching context to '%s'" % arguments["cluster"])

        run_command(command=arguments["command"], cluster_context=arguments["cluster"],
                    application=arguments["application"], results_file=arguments["results_file"])
    else:
        with temporary_kubernetes_cluster() as cluster_context:
            run_command(command=arguments["command"], cluster_context=cluster_context,
                        application=arguments["application"], results_file=arguments["results_file"])
