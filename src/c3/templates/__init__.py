
import os
from string import Template
from pathlib import Path

# template file names
COMPONENT_SETUP_CODE = 'component_setup_code.py'
GW_COMPONENT_SETUP_CODE = 'gw_component_setup_code.py'
DOCKERFILE_FILE = 'dockerfile_template'
KFP_COMPONENT_FILE = 'kfp_component_template.yaml'
KUBERNETES_JOB_FILE = 'kubernetes_job_template.job.yaml'
GRID_WRAPPER_FILE = 'grid_wrapper_template.py'
COS_GRID_WRAPPER_FILE = 'cos_grid_wrapper_template.py'

# load templates
template_path = Path(os.path.dirname(__file__))

with open(template_path / COMPONENT_SETUP_CODE, 'r') as f:
    component_setup_code = f.read()

with open(template_path / GW_COMPONENT_SETUP_CODE, 'r') as f:
    gw_component_setup_code = f.read()

with open(template_path / DOCKERFILE_FILE, 'r') as f:
    dockerfile_template = Template(f.read())

with open(template_path / KFP_COMPONENT_FILE, 'r') as f:
    kfp_component_template = Template(f.read())

with open(template_path / KUBERNETES_JOB_FILE, 'r') as f:
    kubernetes_job_template = Template(f.read())

with open(template_path / GRID_WRAPPER_FILE, 'r') as f:
    grid_wrapper_template = Template(f.read())

with open(template_path / COS_GRID_WRAPPER_FILE, 'r') as f:
    cos_grid_wrapper_template = Template(f.read())
