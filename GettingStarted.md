# Getting started with CLAIMED

The [CLAIMED framework](https://github.com/claimed-framework) enables ease-of-use development and deployment of cloud native data processing applications on Kubernetes using operators and workflows.  

A central tool of **CLAIMED is the Claimed Component Compiler (C3)** which creates a docker image with all dependencies, pushes the container to a registry, and creates a kubernetes-job.yaml as well as a kubeflow-pipeline-component.yaml.
The following explains how to build operators yourself.

## C3 requirements

Your operator script has to follow certain requirements to be processed by C3.

#### Python scripts

- The operator name is the python file:`your_operator_name.py`
- The operator description is the first doc string in the script: `"""Operator description"""`
- You need to provide the required pip packages in comments starting: `# pip install <package1> <package2>`
- The interface is defined by environment variables `your_parameter = os.getenv('your_parameter')`. Output variables start with `output_<name>`.
- You can cast a specific type by wrapping `os.getenv()` with `int()`, `float()`, `bool()`. The default type is string. Only these four types are currently supported. You can use `None` as a default value but not pass the `NoneType` via the `job.yaml`.

#### iPython notebooks

- The operator name is the notebook file:`your_operator_name.ipynb`
- The notebook is converted to a python script before creating the operator by merging all cells. 
- Markdown cells are converted into doc strings. shell commands with `!...` are converted into `os.system()`.
- The requirements of python scripts apply to the notebook code (The operator description can be a markdown cell).

## Compile an operator with C3

With a running Docker engine and your operator script matching the C3 requirements, you can execute the C3 compiler by running `generate_kfp_component.py`:

```sh
python <path/to/c3>/src/c3/generate_kfp_component.py --file_path "<your-operator-script>.py" --version "X.X" --repository "us.icr.io/<namespace>" --additional_files "[file1,file2]"     
```

The `file_path` can point to a python script or an ipython notebook. It is recommended to increase the `version` with every compilation as clusters pull images of a specific version from the cache if you used the image before.
`additional_files` is an optional parameter and must include all files your using in your operator script. The additional files are placed within the same directory as the operator script. 

