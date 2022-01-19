# Thesis Experiment
This repository contains the code needed to run the experiments and process the results for Adriaan Knapen's thesis "[Chaos Engineering Testing for Containerized Multi-Version Deployments](https://www.overleaf.com/read/yxzbstvysmsf)" [[KTH (Final version)](https://urn.kb.se/resolve?urn=urn:nbn:se:kth:diva-291281)] [[Aalto (Final version)](https://aaltodoc.aalto.fi/handle/123456789/103124)]. Individual parts of this tool are stored in their own directory:

* **Evaluation tool**: Runs the experiment and collects results.
* **Results**: Contains the raw measurement results collected using the evaluation tool.
* **Analysis**: Renders plots of the results.

## Evaluation Tool

### Requirements

You need to have the following available on your system:
* Python 3.8, or newer
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

## Results

The results for the executed tests can be found in the `./results/` folder. Each of the files contains the results for one setup using JSON Lines (`.jsonl`) file format. Each measurement is stored on a separate line as a JSON object without nesting. The keys of the object are the name of the metric.

## Analysis

Contains a Jupyter notebook to generate the plots from the data directory. It assumes that the results are stored in the `../results/` relative to the notebook stored in `./analysis/notebook.ipynb`.

The plots are automatically published to Github Pages:

`https://aknapen.nl/thesis-experiment/box_and_scatter_plot-{metric}.{file_type}`

Where `{metric}` can be `restarts`, `time_to_first_request`, `time_to_all_requests` or `time_to_initialize`. The supported values for `{file_type}` are `pdf`, `png`, `jpg` and `svg`.

#### SVG

[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-restarts.svg)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-restarts.svg)
[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_first_request.svg)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_first_request.svg)
[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_all_requests.svg)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_all_requests.svg)
[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_initialize.svg)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_initialize.svg)

#### PNG

[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-restarts.png)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-restarts.png)
[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_first_request.png)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_first_request.png)
[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_all_requests.png)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_all_requests.png)
[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_initialize.png)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_initialize.png)

#### JPG

[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-restarts.jpg)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-restarts.jpg)
[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_first_request.jpg)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_first_request.jpg)
[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_all_requests.jpg)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_all_requests.jpg)
[![](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_initialize.jpg)](https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_initialize.jpg)


#### PDF

* https://aknapen.nl/thesis-experiment/box_and_scatter_plot-restarts.pdf
* https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_first_request.pdf
* https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_all_requests.pdf
* https://aknapen.nl/thesis-experiment/box_and_scatter_plot-time_to_initialize.pdf
