import os
import sys
import re
import logging
import shutil
from string import Template
from io import StringIO
from enum import Enum
from pythonscript import Pythonscript
from notebook_converter import convert_notebook


def generate_component(file_path: str, repository: str, version: str, additional_files: str = None):
    root = logging.getLogger()
    root.setLevel('INFO')

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel('INFO')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)

    logging.info('Parameters: ')
    logging.info('file_path: ' + file_path)
    logging.info('repository: ' + repository)
    logging.info('version: ' + version)
    logging.info('additional_files: ' + str(additional_files))

    if file_path.endswith('.ipynb'):
        logging.info('Convert notebook to python script')
        file_path = convert_notebook(file_path)

    if file_path.endswith('.py'):
        py = Pythonscript(file_path)
        name = py.get_name()
        description = py.get_description() + " CLAIMED v" + version
        inputs = py.get_inputs()
        outputs = py.get_outputs()
        requirements = py.get_requirements()
    else:
        print('Please provide a file_path to a jupyter notebook or python script.')
        raise NotImplementedError

    print(name)
    print(description)
    print(inputs)
    print(outputs)
    print(requirements)

    def check_variable(var_name):
        return var_name in locals() or var_name in globals()

    target_code = file_path.split('/')[-1]
    if file_path != target_code:
        shutil.copy(file_path, target_code)
    if check_variable('additional_files'):
        if additional_files.startswith('['):
            additional_files_path = 'additional_files_path'
            if not os.path.exists(additional_files_path):
                os.makedirs(additional_files_path)
            additional_files_local = additional_files_path
            additional_files = additional_files[1:-1].split(',')
            print('Additional files to add to container:')
            for additional_file in additional_files:
                print(additional_file)
                shutil.copy(additional_file, additional_files_local)
            print(os.listdir(additional_files_path))
        else:
            additional_files_local = additional_files.split('/')[-1:][0]
            shutil.copy(additional_files, additional_files_local)
    else:
        additional_files_local = target_code  # hack
        additional_files_path = None
    file = target_code

    # read and replace '!pip' in notebooks
    with open(file, 'r') as fd:
        text, counter = re.subn(r'!pip', '#!pip', fd.read(), re.I)

    # check if there is at least a  match
    if counter > 0:
        # edit the file
        with open(file, 'w') as fd:
            fd.write(text)

    requirements_docker = list(map(lambda s: 'RUN ' + s, requirements))
    requirements_docker = '\n'.join(requirements_docker)

    python_command = 'python' if target_code.endswith('.py') else 'ipython'

    docker_file = f"""
    FROM registry.access.redhat.com/ubi8/python-39 
    USER root
    RUN dnf install -y java-11-openjdk
    USER default
    RUN pip install ipython==8.6.0 nbformat==5.7.0
    {requirements_docker}
    ADD {additional_files_local} /opt/app-root/src/
    ADD {target_code} /opt/app-root/src/
    USER root
    RUN chmod -R 777 /opt/app-root/src/
    USER default
    CMD ["{python_command}", "/opt/app-root/src/{target_code}"]
    """

    # Remove packages that are not used for python scripts
    if target_code.endswith('.py'):
        docker_file = docker_file.replace('RUN pip install ipython==8.6.0 nbformat==5.7.0\n', '')

    with open("Dockerfile", "w") as text_file:
        text_file.write(docker_file)

    os.system('cat Dockerfile')
    os.system(f'docker build --platform=linux/amd64 -t `echo claimed-{name}:{version}` .')
    os.system(f'docker tag  `echo claimed-{name}:{version}` `echo {repository}/claimed-{name}:{version}`')
    os.system(f'docker tag  `echo claimed-{name}:{version}` `echo {repository}/claimed-{name}:latest`')
    os.system(f'docker push `echo {repository}/claimed-{name}:{version}`')
    os.system(f'docker push `echo {repository}/claimed-{name}:latest`')
    parameter_type = Enum('parameter_type', ['INPUT', 'OUTPUT'])

    def get_component_interface(parameters, type: parameter_type):
        template_string = str()
        for parameter_name, parameter_options in parameters.items():
            default = ''
            if parameter_options['default'] is not None and type == parameter_type.INPUT:
                default = f", default: {parameter_options['default']}"
            template_string += f"- {{name: {parameter_name}, type: {parameter_options['type']}, description: {parameter_options['description']}{default}}}"
            template_string += '\n'
        return template_string

    def get_output_name():
        for output_key, output_value in outputs.items():
            return output_key

    def get_input_for_implementation():
        with StringIO() as inputs_str:
            for input_key, input_value in inputs.items():
                t = Template("        - {inputValue: $name}")
                print(t.substitute(name=input_key), file=inputs_str)
            return inputs_str.getvalue()

    def get_parameter_list():
        return_value = str()
        index = 0
        for output_key, output_value in outputs.items():
            return_value = return_value + output_key + '="${' + str(index) + '}" '
            index = index + 1
        for input_key, input_value in inputs.items():
            return_value = return_value + input_key + '="${' + str(index) + '}" '
            index = index + 1
        return return_value

    t = Template('''name: $name
description: $description

inputs:
$inputs

implementation:
    container:
        image: $container_uri:$version
        command:
        - sh
        - -ec
        - |
          $python $call
$input_for_implementation''')

    yaml = t.substitute(
        name=name,
        description=description,
        inputs=get_component_interface(inputs, parameter_type.INPUT),
        container_uri=f"{repository}/claimed-{name}",
        version=version,
        outputPath=get_output_name(),
        input_for_implementation=get_input_for_implementation(),
        call=f'./{target_code} {get_parameter_list()}',
        python=python_command,
    )

    print(yaml)
    target_yaml_path = file_path.replace('.ipynb', '.yaml').replace('.py', '.yaml')

    with open(target_yaml_path, "w") as text_file:
        text_file.write(yaml)

    # get environment entries
    env_entries = []
    for input_key, _ in inputs.items():
        env_entry = f"        - name: {input_key}\n          value: value_of_{input_key}"
        env_entries.append(env_entry)
        env_entries.append('\n')
    # TODO: Is it possible that a component has no inputs?
    if len(env_entries) != 0:
        env_entries.pop(-1)
    env_entries = ''.join(env_entries)

    job_yaml = f'''apiVersion: batch/v1
kind: Job
metadata:
  name: {name}
spec:
  template:
    spec:
      containers:
      - name: {name}
        image: {repository}/claimed-{name}:{version}
        command: ["/opt/app-root/bin/{python_command}","/opt/app-root/src/{target_code}"]
        env:
{env_entries}
      restartPolicy: OnFailure
      imagePullSecrets:
        - name: image_pull_secret'''

    print(job_yaml)
    target_job_yaml_path = file_path.replace('.ipynb', '.job.yaml').replace('.py', '.job.yaml')

    with open(target_job_yaml_path, "w") as text_file:
        text_file.write(job_yaml)

    # remove local files
    os.remove(target_code)
    os.remove('Dockerfile')
    if additional_files_path is not None:
        shutil.rmtree(additional_files_path, ignore_errors=True)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--file_path', type=str, required=True,
                        help='Path to python script or notebook')
    parser.add_argument('--repository', type=str, required=True,
                        help='Container registry address, e.g. docker.io/<your_username>')
    parser.add_argument('--version', type=str, required=True,
                        help='Image version')
    parser.add_argument('--additional_files', type=str,
                        help='Comma-separated list of paths to additional files to include in the container image')

    args = parser.parse_args()

    generate_component(**vars(args))
