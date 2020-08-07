import argparse
import json
import subprocess
import time
from contextlib import contextmanager
from typing import Iterator, TypedDict, Optional, Union, Iterable

with open("postgresql-ha/load.sql") as load_sql:
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
                "command": [
                    'psql',
                    '-h', 'postgresql-ha-pgpool',  # Set the host
                    '-p', '5432',  # The port
                    '-U', 'postgres',  # The user
                    '-d', 'postgres',  # The database
                    '-c', load_sql.read(),  # The SQL to run
                ]
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


class Cluster(TypedDict):
    contextName: str


@contextmanager
def temporary_kubernetes_cluster(name: str = "temp", region: str = 'ams3') -> Iterator[Cluster]:
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


def parse_arguments() -> Arguments:
    parser = argparse.ArgumentParser()
    parser.add_argument('command', type=str, choices=['test', 'deploy', 'destroy', 'all'], default='all')
    parser.add_argument('application', type=str, choices=APPLICATIONS.keys())
    parser.add_argument('--cluster', type=str,
                        help='The name of the cluster to use, if left empty a temporary cluster will be created.')
    args = parser.parse_args()

    return {
        'cluster': args.cluster,
        'command': args.command,
        'application': args.application,
    }


def create_namespace(name: str):
    return subprocess.run(["kubectl", "create", "namespace", name])


def deploy(namespace: str, name: str, chart: str, values: str, version: str):
    return subprocess.run([
        "helm", "install", name, chart,
        "-f", values,
        "--namespace", namespace,
        "--version", version,
    ])


def destroy_deployment(namespace: str):
    return subprocess.run([
        # Overwriting context breaks helmsman
        "helm", "delete", "postgresql-ha", "--namespace", namespace
    ])


def destroy_namespace(namespace: str):
    return subprocess.run([
        "kubectl", "delete", "namespace", namespace
    ])


def get_pods_data() -> dict:
    query = subprocess.run([
        "kubectl", "get", "pods", "--output", "json",
    ], stdout=subprocess.PIPE, text=True)

    if query.returncode > 0:
        raise Exception(f"Failed retrieving pod data: {query.stderr}")

    return json.loads(query.stdout)


def get_container_statuses() -> Iterable:
    pods_data = get_pods_data()

    yield from (container_status
                for pod in pods_data["items"]
                for container_status in pod["status"].get("containerStatuses", [])
                )


def run_test(namespace: str, workload):
    def execute_workload_test():
        return subprocess.run([
            'kubectl', 'run', 'workload', '--rm', '--tty', '-i', '--restart', 'Never',
            '--namespace', namespace, '--image', workload["image"],
            *[x for name, value in workload["env"].items() for x in ("--env", f"{name}={value}")],
            '--command', '--', *workload["command"],
        ])

    # Register the starting time
    start_time = time.time()
    print("Starting time: ", start_time)

    # Define a variable to hold the metrics we are collecting
    metrics: dict = {
        'time_to_initialize': None,
        'time_to_first_request': None,
        # 'time_to_all_requests': None,
    }

    def all_containers_initialized() -> bool:
        # Check if all containers are ready
        container_statuses = get_container_statuses()

        # Check if all containers initialized
        return all(map(lambda x: x["ready"], container_statuses))

    def can_handle_request() -> bool:
        # Run a small workload as to test if it is functional
        workload_result = execute_workload_test()

        # Inspect the status code to see if our workload test was successful
        return workload_result.returncode == 0

    def amount_of_restarts() -> int:
        return sum(container_status["restartCount"] for container_status in get_container_statuses())

    # Collect time based metrics until all are acquired
    while not all(metrics.values()):
        # Check if all containers are ready
        if not metrics["time_to_initialize"]:
            if all_containers_initialized():
                metrics["time_to_initialize"] = time.time()

        # Check if the application can process a workload
        if not metrics["time_to_first_request"]:
            if can_handle_request():
                metrics["time_to_first_request"] = time.time()

    # Measure finish time
    for name, end_time in metrics.items():
        print(f"{name}: {end_time - start_time}")

    # Detect amount of restarts
    print(f"restarts: {amount_of_restarts()}")


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


def run_command(command: Command, cluster_context: str, application: str):
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
        run_test(app_config["namespace"], app_config["workload"])
    elif command == "all":
        run_command("deploy", cluster_context, application)
        run_command("test", cluster_context, application)
        run_command("destroy", cluster_context, application)
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
                    application=arguments["application"])
    else:
        with temporary_kubernetes_cluster() as cluster:
            run_command(command=arguments["command"], cluster_context=cluster["contextName"],
                        application=arguments["application"])
