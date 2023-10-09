import os
import sys
import re
import logging
import shutil
import argparse
from string import Template
from io import StringIO
from pythonscript import Pythonscript
from notebook_converter import convert_notebook
from templates import component_setup_code, dockerfile_template, kfp_component_template, kubernetes_job_template

CLAIMED_VERSION = 'V0.1'


def create_operator(file_path: str,
                    repository: str,
                    version: str,
                    dockerfile_template: str,
                    additional_files: str = None,
                    ):
    logging.info('Parameters: ')
    logging.info('file_path: ' + file_path)
    logging.info('repository: ' + repository)
    logging.info('version: ' + version)
    logging.info('additional_files: ' + str(additional_files))

    if file_path.endswith('.ipynb'):
        logging.info('Convert notebook to python script')
        target_code = convert_notebook(file_path)
    else:
        target_code = file_path.split('/')[-1]
        if file_path == target_code:
            # use temp file for processing
            target_code = 'claimed_' + target_code
        # Copy file to current working directory
        shutil.copy(file_path, target_code)

    if target_code.endswith('.py'):
        # Add code for logging and cli parameters to the beginning of the script
        with open(target_code, 'r') as f:
            script = f.read()
        script = component_setup_code + script
        with open(target_code, 'w') as f:
            f.write(script)

    # getting parameter from the script
    if target_code.endswith('.py'):
        py = Pythonscript(target_code)
        name = py.get_name()
        # convert description into a string with a single line
        description = ('"' + py.get_description().replace('\n', ' ').replace('"', '\'') +
                       ' – CLAIMED ' + CLAIMED_VERSION + '"')
        inputs = py.get_inputs()
        outputs = py.get_outputs()
        requirements = py.get_requirements()
    else:
        raise NotImplementedError('Please provide a file_path to a jupyter notebook or python script.')
    
    # Strip 'claimed-' from name of copied temp file
    if name.startswith('claimed-'):
        name = name[8:]

    logging.info('Operator name: ' + name)
    logging.info('Description:: ' + description)
    logging.info('Inputs: ' + str(inputs))
    logging.info('Outputs: ' + str(outputs))
    logging.info('Requirements: ' + str(requirements))

    if additional_files is not None:
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
            # ensure the original file is not deleted later
            if additional_files != additional_files_local:
                additional_files_path = additional_files_local
            else:
                additional_files_path = None
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

    docker_file = dockerfile_template.substitute(
        requirements_docker=requirements_docker,
        target_code=target_code,
        additional_files_local=additional_files_local,
    )

    logging.info('Create Dockerfile')
    with open("Dockerfile", "w") as text_file:
        text_file.write(docker_file)

    logging.info(f'Build and push image to {repository}/claimed-{name}:{version}')
    os.system(f'docker build --platform=linux/amd64 -t `echo claimed-{name}:{version}` .')
    os.system(f'docker tag  `echo claimed-{name}:{version}` `echo {repository}/claimed-{name}:{version}`')
    os.system(f'docker tag  `echo claimed-{name}:{version}` `echo {repository}/claimed-{name}:latest`')
    os.system(f'docker push `echo {repository}/claimed-{name}:latest`')
    os.system(f'docker push `echo {repository}/claimed-{name}:{version}`')

    def get_component_interface(parameters):
        template_string = str()
        for parameter_name, parameter_options in parameters.items():
            template_string += f'- {{name: {parameter_name}, type: {parameter_options["type"]}, description: "{parameter_options["description"]}"'
            if parameter_options['default'] is not None:
                template_string += f', default: {parameter_options["default"]}'
            template_string += '}\n'
        return template_string

    def get_output_name():
        for output_key, output_value in outputs.items():
            return output_key

    # TODO: Review implementation
    def get_input_for_implementation():
        t = Template("        - {inputValue: $name}")
        with StringIO() as inputs_str:
            for input_key, input_value in inputs.items():
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

    yaml = kfp_component_template.substitute(
        name=name,
        description=description,
        repository=repository,
        version=version,
        inputs=get_component_interface(inputs),
        outputs=get_component_interface(outputs),
        call=f'./{target_code} {get_parameter_list()}',
        input_for_implementation=get_input_for_implementation(),
    )

    logging.debug('KubeFlow component yaml:')
    logging.debug(yaml)
    target_yaml_path = file_path.replace('.ipynb', '.yaml').replace('.py', '.yaml')

    logging.debug(f' Write KubeFlow component yaml to {target_yaml_path}')
    with open(target_yaml_path, "w") as text_file:
        text_file.write(yaml)

    # get environment entries
    # TODO: Make it similar to the kfp code
    env_entries = []
    for input_key, _ in inputs.items():
        env_entry = f"        - name: {input_key}\n          value: value_of_{input_key}"
        env_entries.append(env_entry)
        env_entries.append('\n')
    for output_key, _ in outputs.items():
        env_entry = f"        - name: {output_key}\n          value: value_of_{output_key}"
        env_entries.append(env_entry)
        env_entries.append('\n')

    # TODO: Is it possible that a component has no inputs?
    if len(env_entries) != 0:
        env_entries.pop(-1)
    env_entries = ''.join(env_entries)

    job_yaml = kubernetes_job_template.substitute(
        name=name,
        repository=repository,
        version=version,
        target_code=target_code,
        env_entries=env_entries,
    )

    logging.debug('Kubernetes job yaml:')
    logging.debug(job_yaml)
    target_job_yaml_path = file_path.replace('.ipynb', '.job.yaml').replace('.py', '.job.yaml')

    logging.info(f'Write kubernetes job yaml to {target_job_yaml_path}')
    with open(target_job_yaml_path, "w") as text_file:
        text_file.write(job_yaml)

    logging.info(f'Remove local files')
    # remove temporary files
    if file_path != target_code:
        os.remove(target_code)
    os.remove('Dockerfile')
    if additional_files_path is not None:
        shutil.rmtree(additional_files_path, ignore_errors=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file_path', type=str, required=True,
                        help='Path to python script or notebook')
    parser.add_argument('-r', '--repository', type=str, required=True,
                        help='Container registry address, e.g. docker.io/<your_username>')
    parser.add_argument('-v', '--version', type=str, required=True,
                        help='Image version')
    parser.add_argument('-a', '--additional_files', type=str,
                        help='Comma-separated list of paths to additional files to include in the container image')
    parser.add_argument('-l', '--log_level', type=str, default='INFO')
    parser.add_argument('--dockerfile_template_path', type=str, default='',
                        help='Path to custom dockerfile template')
    args = parser.parse_args()

    # Init logging
    root = logging.getLogger()
    root.setLevel(args.log_level)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    handler.setLevel(args.log_level)
    root.addHandler(handler)

    # Update dockerfile template if specified
    if args.dockerfile_template_path != '':
        logging.info(f'Uses custom dockerfile template from {args.dockerfile_template_path}')
        with open(args.dockerfile_template_path, 'r') as f:
            dockerfile_template = Template(f.read())

    create_operator(
        file_path=args.file_path,
        repository=args.repository,
        version=args.version,
        dockerfile_template=dockerfile_template,
        additional_files=args.additional_files
    )
