import argparse
import json
import subprocess
import time
from contextlib import contextmanager
from typing import Iterator, TypedDict, Optional, Union


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


def parse_arguments() -> Arguments:
    parser = argparse.ArgumentParser()
    parser.add_argument('command', type=str, choices=['test', 'deploy', 'destroy', 'all'], default='all')
    parser.add_argument('--cluster', type=str,
                        help='The name of the cluster to use, if left empty a temporary cluster will be created.')
    args = parser.parse_args()

    return {
        'cluster': args.cluster,
        'command': args.command,
    }


def deploy(cluster_context: str):
    return subprocess.run([
        "helmsman", "-f", "helmsman.yaml", "-apply",
    ])


def destroy(cluster_context: str):
    return subprocess.run([
        # Overwriting context breaks helmsman
        "helmsman", "-f", "helmsman.yaml", "-destroy",
    ])


def get_pods_data() -> dict:
    query = subprocess.run([
        "kubectl", "get", "pods", "--output", "json",
    ], stdout=subprocess.PIPE, text=True)

    if query.returncode > 0:
        raise Exception(f"Failed retrieving pod data: {query.stderr}")

    return json.loads(query.stdout)


def run_test():
    def execute_workload_test():
        with open("load.sql", "r") as load_sql:
            return subprocess.run([
                'kubectl', 'run', 'postgresql-ha-client', '--rm', '--tty', '-i', '--restart', 'Never', '--namespace',
                'postgresql-ha', '--image', 'bitnami/postgresql:11', '--env', 'PGPASSWORD=password', '--env',
                'PGCONNECT_TIMEOUT=1', '--command',
                '--', 'psql', '-h', 'postgresql-ha-pgpool', '-p', '5432', '-U', 'postgres', '-d', 'postgres', '-c',
                load_sql.read()
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
        # Collect the status of all our pods
        pod_data = get_pods_data()

        # Check if all containers are ready
        container_statuses = [container_status
                              for pod in pod_data["items"]
                              for container_status in pod["status"]["containerStatuses"]
                              ]

        # Check if all containers initialized
        return all(map(lambda x: x["ready"], container_statuses))

    def can_handle_request() -> bool:
        # Run a small workload as to test if it is functional
        workload_result = execute_workload_test()

        # Inspect the status code to see if our workload test was successful
        return workload_result.returncode == 0

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
    pass  # @todo


def run_command(command: Command, cluster_context: str):
    if command == "deploy":
        deploy(cluster_context)
    elif command == "destroy":
        destroy(cluster_context)
    elif command == "test":
        run_test()
    elif command == "all":
        run_command("deploy", cluster_context)
        run_command("test", cluster_context)
        run_command("destroy", cluster_context)
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

        run_command(command=arguments["command"], cluster_context=arguments["cluster"])
    else:
        with temporary_kubernetes_cluster() as cluster:
            run_command(command=arguments["command"], cluster_context=cluster["contextName"])
