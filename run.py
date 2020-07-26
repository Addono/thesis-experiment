import subprocess
from contextlib import contextmanager
from typing import Iterator, TypedDict, Optional
import argparse
import time

class Cluster(TypedDict):
  contextName: str

@contextmanager
def temporary_kubernetes_cluster(name: str = "temp", region: str = 'ams3') -> Iterator[Cluster]:
  create = subprocess.run(['doctl', 'kubernetes', 'cluster', 'create', '--region', region , name])
  
  if create.returncode > 0:
    raise Exception("Failed creating Kubernetes cluster")

  yield {'contextName': f"do-{region}-{name}"}

  delete = subprocess.run(['doctl', 'kubernetes', 'cluster', 'delete', name, '-f'])

  if delete.returncode > 0:
    raise Exception("Failed deleting Kubernetes cluster")


class Arguments(TypedDict):
  cluster: Optional[str]

def parse_arguments() -> Arguments:
  parser = argparse.ArgumentParser()
  parser.add_argument('--cluster', type=str, help='The name of the cluster to use, if left empty a temporary cluster will be created.')
  args = parser.parse_args()

  return {
    'cluster': args.cluster
  }

def run_tests(cluster_context: str):
  # Register the starting time
  start_time = time.time()
  print("Starting time: ", start_time)

  # Initiate deployment
  helmsmanDeploy = subprocess.run(["helmsman", "-f", "helmsman.yaml", "-apply", "-context-override", cluster_context])

  # Check if deployment is up
  while True:
    with open("load.sql", "r") as load_sql:
      applyLoad = subprocess.run([
        'kubectl', 'run', 'postgresql-ha-client', '--rm', '--tty', '-i', '--restart', 'Never', '--namespace', 'postgresql-ha', '--image', 'bitnami/postgresql:11', '--env', 'PGPASSWORD=password', '--env', 'PGCONNECT_TIMEOUT=1', '--command', 
        '--', 'psql', '-h', 'postgresql-ha-pgpool', '-p', '5432', '-U', 'postgres', '-d', 'postgres', '-c', load_sql.read()
      ])

    # Loop until our test succeeded
    if applyLoad.returncode == 0:
      break

  # Measure finish time
  end_time = time.time()
  print("End time: ", end_time, "Duration: ", end_time - start_time)

  # Detect amount of restarts
  pass # @todo

if __name__ == "__main__":
  # Retrieve the arguments
  arguments = parse_arguments()  

  # Skip creating a temporary cluster if one is specified to be used
  if arguments["cluster"]:
    # Switch context in case we are not yet on the one indicated
    context_switch = subprocess.run(["kubectx", arguments["cluster"]])

    if context_switch.returncode > 0:
      raise Exception("Failed switching context to '%s'" % arguments["cluster"])

    run_tests(cluster_context=arguments["cluster"])
  else:
    with temporary_kubernetes_cluster() as cluster:
      run_tests(cluster["contextName"])
  