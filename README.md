# Thesis Experiment
This repository contains the code needed to run the experiments and process the results for Adriaan Knapen's thesis "[Chaos Engineering Testing for Containerized Multi-Version Deployments](https://www.overleaf.com/read/yxzbstvysmsf)". Individual parts of this tool are stored in their own directory:

* **Evaluation tool**: Runs the experiment and collects results.
* **Results**: Contains the raw measurement results collected using the evaluation tool.
* **Analysis**: Renders plots of the results.

---

## Evaluation Tool

### Requirements

You need to have the following available on your system:
* Python 3
* `kubectl`
* `kubectx`
* Helm 3
* If you want it to create a new and temporary Kubernetes cluster, then you need Digital Ocean CLI (`doctl`) locally available and authenticated

### Getting started

Open a terminal in the `evaluation-tool` directory and install the dependencies:

```bash
pip install -r requirements.txt
```

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

