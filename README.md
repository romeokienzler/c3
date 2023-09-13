[![OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/projects/6718/badge)](https://bestpractices.coreinfrastructure.org/projects/6718)
[![GitHub](https://img.shields.io/badge/issue_tracking-github-blue.svg)](https://github.com/claimed-framework/component-library/issues)



# C3 - the CLAIMED Component Compiler

**TL;DR**
- takes arbitrary assets (Jupyter notebooks, python/R/shell/SQL scripts) as input
- automatically creates container images and pushes to container registries
- automatically installs all required dependencies into the container image
- creates KubeFlow Pipeline components (target workflow execution engines are pluggable)
- can be triggered from CICD pipelines


To learn more on how this library works in practice, please have a look at the following [video](https://www.youtube.com/watch?v=FuV2oG55C5s)

## Related work
[Ploomber](https://github.com/ploomber/ploomber)

[Orchest](https://www.orchest.io/)

## Getting started 

### Install

Download the code from https://github.com/claimed-framework/c3/tree/main and install the package.

```sh
git clone claimed-framework/c3
cd c3
pip install -e src
```

### Usage

Run `generate_kfp_component.ipynb` with ipython and provide the required additional information (`notebook_path`, `version`, `repository`, optional: `additionl_files`).

Example from the `c3` project root. Remember to add `../<your_project_name>/` when select your notebook path. Note that the code creates containers and therefore requires a running docker instance.
```sh
ipython src/c3/generate_kfp_component.ipynb notebook_path="<your_component_path>" version="<X.X>" additionl_files="[file1,file2]" repository="docker.io/<your_repo>"
```

### Notebook requirements

The c3 compiler requires your notebook to follow a certain pattern:

1. Cell: Markdown with the component name
2. Cell: Markdown with the component description
3. Cell: Requirements installed by pip, e.g., `!pip install <package1> <package2> <...>`
4. Cell: Imports, e.g., `import numpy as np`
5. Cell: Component interface, e.g., `input_path = os.environ.get('input_path')`. Output variables have to start with `output`, more details in the following.
6. Cell and following: Your code

### Component interface

The interface consists of input and output variables that are defined by environment variables. Output variables have to start with `output`, e.g., `output_path`. 
Environment variables and arguments are by default string values. You can cast a specific type by wrapping the `os.environ.get()` into the methods `bool()`, `int()`, or `float()`.
The c3 compiler cannot handle other types than string, boolean, integer, and float values.

```py
input_string = os.environ.get('input_string', 'default_value')
input_bool = bool(os.environ.get('input_bool', False))
input_int = int(os.environ.get('input_int'))
input_float = float(os.environ.get('input_float'))
```

## Getting Help

We welcome your questions, ideas, and feedback. Please create an [issue](https://github.com/claimed-framework/component-library/issues) or a [discussion thread](https://github.com/claimed-framework/component-library/discussions).
Please see [VULNERABILITIES.md](VULNERABILITIES.md) for reporting vulnerabilities.

## Contributing to CLAIMED
Interested in helping make CLAIMED better? We encourage you to take a look at our 
[Contributing](CONTRIBUTING.md) page.

## License
This software is released under Apache License v2.0
