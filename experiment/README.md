# Thesis Experiment
This repository contains the code needed to run the experiments for Adriaan Knapen's thesis "[Chaos Engineering Testing for Containerized Multi-Version Deployments](https://www.overleaf.com/read/yxzbstvysmsf)".

## Requirements
You need to have the following available on your system:
* Python 3
* `kubectl`
* `kubectx`
* Helm 3
* If you want it to create a new and temporary Kubernetes cluster, then you need Digital Ocean CLI (`doctl`) locally available and authenticated

## Getting started

Run the following command to see the help.
```bash
python run.py --help
```

If you want it to create a temporary cluster on Digital Ocean, then it sufices to run:
```bash
python run.py
```

Otherwise you need to have a local context which you want to use for the experiment:
```bash
python run.py --cluster the-name-of-my-k8s-context
```

