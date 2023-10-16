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

Just run the following command with your python script or notebook: 
```sh
python <path/to/c3>/src/c3/create_operator.py --file_path "<your-operator-script>.py" --version "X.X" --repository "<registry>/<namespace>" --additional_files "[file1,file2]"
```

Your code needs to follow certain requirements which are explained in [Getting Started](GettingStarted.md). 


## Getting Help

```sh
python src/c3/create_operator.py --help
```

We welcome your questions, ideas, and feedback. Please create an [issue](https://github.com/claimed-framework/component-library/issues) or a [discussion thread](https://github.com/claimed-framework/component-library/discussions).
Please see [VULNERABILITIES.md](VULNERABILITIES.md) for reporting vulnerabilities.

## Contributing to CLAIMED
Interested in helping make CLAIMED better? We encourage you to take a look at our 
[Contributing](CONTRIBUTING.md) page.

## License
This software is released under Apache License v2.0
