
import os
import sys
import logging
import shutil
import argparse
import subprocess
from string import Template
from c3.pythonscript import Pythonscript
from c3.utils import convert_notebook, get_image_version
from c3.templates import component_setup_code, dockerfile_template, kfp_component_template, kubernetes_job_template

CLAIMED_VERSION = 'V0.1'


def create_operator(file_path: str,
                    repository: str,
                    version: str,
                    dockerfile_template: str,
                    additional_files: str = None,
                    log_level='INFO',
                    test_mode=False,
                    ):
    logging.info('Parameters: ')
    logging.info('file_path: ' + file_path)
    logging.info('repository: ' + repository)
    logging.info('version: ' + str(version))
    logging.info('additional_files: ' + str(additional_files))

    # TODO: add argument for running ipython instead of python within the container
    if file_path.endswith('.ipynb'):
        logging.info('Convert notebook to python script')
        target_code = convert_notebook(file_path)
    elif file_path.endswith('.py'):
        target_code = file_path.split('/')[-1]
        if file_path == target_code:
            # use temp file for processing
            target_code = 'claimed_' + target_code
        # Copy file to current working directory
        shutil.copy(file_path, target_code)
    else:
        raise NotImplementedError('Please provide a file_path to a jupyter notebook or python script.')

    if target_code.endswith('.py'):
        # Add code for logging and cli parameters to the beginning of the script
        with open(target_code, 'r') as f:
            script = f.read()
        script = component_setup_code + script
        with open(target_code, 'w') as f:
            f.write(script)

        # getting parameter from the script
        py = Pythonscript(target_code)
        name = py.get_name()
        # convert description into a string with a single line
        description = ('"' + py.get_description().replace('\n', ' ').replace('"', '\'') +
                       ' – CLAIMED ' + CLAIMED_VERSION + '"')
        inputs = py.get_inputs()
        outputs = py.get_outputs()
        requirements = py.get_requirements()
    else:
        raise NotImplementedError('C3 currently only supports jupyter notebook or python script.')
    
    # Strip 'claimed-' from name of copied temp file
    if name.startswith('claimed-'):
        name = name[8:]

    logging.info('Operator name: ' + name)
    logging.info('Description:: ' + description)
    logging.info('Inputs: ' + str(inputs))
    logging.info('Outputs: ' + str(outputs))
    logging.info('Requirements: ' + str(requirements))

    # copy all additional files to temporary folder
    additional_files_path = 'additional_files_path'
    while os.path.exists(additional_files_path):
        # ensures using a new directory
        additional_files_path += '_temp'
    logging.debug(f'Create dir for additional files {additional_files_path}')
    os.makedirs(additional_files_path)
    for additional_file in additional_files:
        assert os.path.isfile(additional_file), \
            f"Could not find file at {additional_file}. Please provide only files as additional parameters."
        shutil.copy(additional_file, additional_files_path)
    logging.info(f'Selected additional files: {os.listdir(additional_files_path)}')

    requirements_docker = list(map(lambda s: 'RUN ' + s, requirements))
    requirements_docker = '\n'.join(requirements_docker)

    docker_file = dockerfile_template.substitute(
        requirements_docker=requirements_docker,
        target_code=target_code,
        additional_files_path=additional_files_path,
    )

    logging.info('Create Dockerfile')
    with open("Dockerfile", "w") as text_file:
        text_file.write(docker_file)
        
    if version is None:
        # auto increase version based on registered images
        version = get_image_version(repository, name)

    logging.info(f'Building container image claimed-{name}:{version}')
    subprocess.run(
        ['docker', 'build', '--platform', 'linux/amd64', '-t', f'claimed-{name}:{version}', '.'],
        stdout=None if log_level == 'DEBUG' else subprocess.PIPE, check=True,
    )
    logging.debug(f'Tagging images with "latest" and "{version}"')
    subprocess.run(
        ['docker', 'tag', f'claimed-{name}:{version}', f'{repository}/claimed-{name}:{version}'],
        stdout=None if log_level == 'DEBUG' else subprocess.PIPE, check=True,
    )
    subprocess.run(
        ['docker', 'tag', f'claimed-{name}:{version}', f'{repository}/claimed-{name}:latest'],
        stdout=None if log_level == 'DEBUG' else subprocess.PIPE, check=True,
    )
    logging.info('Successfully built image')

    logging.info(f'Pushing images to registry {repository}')
    try:
        subprocess.run(
            ['docker', 'push', f'{repository}/claimed-{name}:latest'],
            stdout=None if log_level == 'DEBUG' else subprocess.PIPE, check=True,
        )
        subprocess.run(
            ['docker', 'push', f'{repository}/claimed-{name}:{version}'],
            stdout=None if log_level == 'DEBUG' else subprocess.PIPE, check=True,
        )
        logging.info('Successfully pushed image to registry')
    except Exception as err:
        logging.error(f'Could not push images to namespace {repository}. '
                      f'Please check if docker is logged in or select a namespace with access.')
        if test_mode:
            logging.info('Continue processing (test mode).')
            pass
        else:
            if file_path != target_code:
                os.remove(target_code)
            os.remove('Dockerfile')
            shutil.rmtree(additional_files_path, ignore_errors=True)
            raise err

    def get_component_interface(parameters):
        return_string = str()
        for name, options in parameters.items():
            return_string += f'- {{name: {name}, type: {options["type"]}, description: "{options["description"]}"'
            if options['default'] is not None:
                if not options["default"].startswith('"'):
                    options["default"] = f'"{options["default"]}"'
                return_string += f', default: {options["default"]}'
            return_string += '}\n'
        return return_string
    inputs_list = get_component_interface(inputs)
    outputs_list = get_component_interface(outputs)

    parameter_list = str()
    for index, key in enumerate(list(inputs.keys()) + list(outputs.keys())):
        parameter_list += f'{key}="${{{index}}}" '

    parameter_values = str()
    for input_key in inputs.keys():
        parameter_values += f"        - {{inputValue: {input_key}}}\n"
    for input_key in outputs.keys():
        parameter_values += f"        - {{outputPath: {input_key}}}\n"

    yaml = kfp_component_template.substitute(
        name=name,
        description=description,
        repository=repository,
        version=version,
        inputs=inputs_list,
        outputs=outputs_list,
        call=f'./{target_code} {parameter_list}',
        parameter_values=parameter_values,
    )

    logging.debug('KubeFlow component yaml:\n' + yaml)
    target_yaml_path = file_path.replace('.ipynb', '.yaml').replace('.py', '.yaml')

    logging.info(f'Write KubeFlow component yaml to {target_yaml_path}')
    with open(target_yaml_path, "w") as text_file:
        text_file.write(yaml)

    # get environment entries
    env_entries = str()
    for key in list(inputs.keys()) + list(outputs.keys()):
        env_entries += f"        - name: {key}\n          value: value_of_{key}\n"
    env_entries = env_entries.rstrip()

    job_yaml = kubernetes_job_template.substitute(
        name=name,
        repository=repository,
        version=version,
        target_code=target_code,
        env_entries=env_entries,
    )

    logging.debug('Kubernetes job yaml:\n' + job_yaml)
    target_job_yaml_path = file_path.replace('.ipynb', '.job.yaml').replace('.py', '.job.yaml')

    logging.info(f'Write kubernetes job yaml to {target_job_yaml_path}')
    with open(target_job_yaml_path, "w") as text_file:
        text_file.write(job_yaml)

    logging.info(f'Remove local files')
    # remove temporary files
    if file_path != target_code:
        os.remove(target_code)
    os.remove('Dockerfile')
    shutil.rmtree(additional_files_path, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('FILE_PATH', type=str,
                        help='Path to python script or notebook')
    parser.add_argument('ADDITIONAL_FILES', type=str, nargs='*',
                        help='Paths to additional files to include in the container image')
    parser.add_argument('-r', '--repository', type=str, required=True,
                        help='Container registry address, e.g. docker.io/<username>')
    parser.add_argument('-v', '--version', type=str, default=None,
                        help='Container image version. Auto-increases the version number if not provided (default 0.1)')
    parser.add_argument('-l', '--log_level', type=str, default='INFO')
    parser.add_argument('--dockerfile_template_path', type=str, default='',
                        help='Path to custom dockerfile template')
    parser.add_argument('--test_mode', action='store_true')
    args = parser.parse_args()

    # Init logging
    root = logging.getLogger()
    root.setLevel(args.log_level)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    handler.setLevel(args.log_level)
    root.addHandler(handler)

    # Update dockerfile template if specified
    if args.dockerfile_template_path != '':
        logging.info(f'Uses custom dockerfile template from {args.dockerfile_template_path}')
        with open(args.dockerfile_template_path, 'r') as f:
            _dockerfile_template = Template(f.read())
    else:
        _dockerfile_template = dockerfile_template

    create_operator(
        file_path=args.FILE_PATH,
        repository=args.repository,
        version=args.version,
        dockerfile_template=_dockerfile_template,
        additional_files=args.ADDITIONAL_FILES,
        log_level=args.log_level,
        test_mode=args.test_mode,
    )


if __name__ == '__main__':
    main()
