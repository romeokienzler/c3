
import os
import sys
import logging
import shutil
import argparse
import subprocess
from pathlib import Path
from string import Template
from typing import Optional
from c3.pythonscript import Pythonscript
from c3.rscript import Rscript
from c3.utils import convert_notebook, get_image_version
from c3.templates import (python_component_setup_code, r_component_setup_code,
                          python_dockerfile_template, r_dockerfile_template,
                          kfp_component_template, kubernetes_job_template, cwl_component_template)

CLAIMED_VERSION = 'V0.1'


def create_dockerfile(dockerfile_template, requirements, target_code, additional_files_path, working_dir, command):
    requirements_docker = list(map(lambda s: 'RUN ' + s, requirements))
    requirements_docker = '\n'.join(requirements_docker)

    docker_file = dockerfile_template.substitute(
        requirements_docker=requirements_docker,
        target_code=target_code,
        additional_files_path=additional_files_path,
        working_dir=working_dir,
        command=os.path.basename(command),
    )

    logging.info('Create Dockerfile')
    with open("Dockerfile", "w") as text_file:
        text_file.write(docker_file)


def create_kfp_component(name, description, repository, version, command, target_code, file_path, inputs, outputs):

    inputs_list = str()
    for name, options in inputs.items():
        inputs_list += f'- {{name: {name}, type: {options["type"]}, description: "{options["description"]}"'
        if options['default'] is not None:
            if not options["default"].startswith('"'):
                options["default"] = f'"{options["default"]}"'
            inputs_list += f', default: {options["default"]}'
        inputs_list += '}\n'

    outputs_list = str()
    for name, options in outputs.items():
        outputs_list += f'- {{name: {name}, type: String, description: "{options["description"]}"}}\n'

    parameter_list = str()
    for index, key in enumerate(list(inputs.keys()) + list(outputs.keys())):
        parameter_list += f'{key}="${{{index}}}" '

    parameter_values = str()
    for input_key in inputs.keys():
        parameter_values += f"        - {{inputValue: {input_key}}}\n"
    for output_key in outputs.keys():
        parameter_values += f"        - {{outputPath: {output_key}}}\n"

    yaml = kfp_component_template.substitute(
        name=name,
        description=description,
        repository=repository,
        version=version,
        inputs=inputs_list,
        outputs=outputs_list,
        call=f'{os.path.basename(command)} ./{target_code} {parameter_list}',
        parameter_values=parameter_values,
    )

    logging.debug('KubeFlow component yaml:\n' + yaml)
    target_yaml_path = str(Path(file_path).with_suffix('.yaml'))

    logging.info(f'Write KubeFlow component yaml to {target_yaml_path}')
    with open(target_yaml_path, "w") as text_file:
        text_file.write(yaml)


def create_kubernetes_job(name, repository, version, target_code, command, working_dir, file_path, inputs):
    # get environment entries
    env_entries = str()
    for key in list(inputs.keys()):
        env_entries += f"        - name: {key}\n          value: value_of_{key}\n"
    env_entries = env_entries.rstrip()

    job_yaml = kubernetes_job_template.substitute(
        name=name,
        repository=repository,
        version=version,
        target_code=target_code,
        env_entries=env_entries,
        command=command,
        working_dir=working_dir,
    )

    logging.debug('Kubernetes job yaml:\n' + job_yaml)
    target_job_yaml_path = str(Path(file_path).with_suffix('.job.yaml'))

    logging.info(f'Write kubernetes job yaml to {target_job_yaml_path}')
    with open(target_job_yaml_path, "w") as text_file:
        text_file.write(job_yaml)


def create_cwl_component(name, repository, version, file_path, inputs, outputs):
    # get environment entries
    i = 1
    input_envs = str()
    for input, options in inputs.items():
        i += 1
        input_envs += (f"  {input}:\n    type: string\n    default: {options['default']}\n    "
                       f"inputBinding:\n      position: {i}\n      prefix: --{input}\n")

    if len(outputs) == 0:
        output_envs = '[]'
    else:
        output_envs = '\n'
    for output, options in outputs.items():
        i += 1
        output_envs += (f"  {output}:\n    type: string\n    "
                        f"inputBinding:\n      position: {i}\n      prefix: --{output}\n")

    cwl = cwl_component_template.substitute(
        name=name,
        repository=repository,
        version=version,
        inputs=input_envs,
        outputs=output_envs,
    )

    logging.debug('CWL component:\n' + cwl)
    target_cwl_path = str(Path(file_path).with_suffix('.cwl'))

    logging.info(f'Write cwl component to {target_cwl_path}')
    with open(target_cwl_path, "w") as text_file:
        text_file.write(cwl)


def print_claimed_command(name, repository, version, inputs):
    claimed_command = f"claimed --component {repository}/claimed-{name}:{version}"
    for input, options in inputs.items():
        claimed_command += f" --{input} {options['default']}"
    logging.info(f'Run operators locally with claimed-cli:\n{claimed_command}')


def remove_temporary_files(file_path, target_code, additional_files_path):
    logging.info(f'Remove local files')
    # remove temporary files
    if file_path != target_code:
        os.remove(target_code)
    os.remove('Dockerfile')
    shutil.rmtree(additional_files_path, ignore_errors=True)


def create_operator(file_path: str,
                    repository: str,
                    version: str,
                    custom_dockerfile_template: Optional[Template],
                    additional_files: str = None,
                    log_level='INFO',
                    test_mode=False,
                    no_cache=False,
                    ):
    logging.info('Parameters: ')
    logging.info('file_path: ' + file_path)
    logging.info('repository: ' + repository)
    logging.info('version: ' + str(version))
    logging.info('additional_files: ' + str(additional_files))

    if file_path.endswith('.ipynb'):
        logging.info('Convert notebook to python script')
        target_code = convert_notebook(file_path)
        command = '/opt/app-root/bin/ipython'
        working_dir = '/opt/app-root/src/'

    elif file_path.endswith('.py'):
        target_code = file_path.split('/')[-1]
        if file_path == target_code:
            # use temp file for processing
            target_code = 'claimed_' + target_code
        # Copy file to current working directory
        shutil.copy(file_path, target_code)
        command = '/opt/app-root/bin/python'
        working_dir = '/opt/app-root/src/'

    elif file_path.lower().endswith('.r'):
        target_code = file_path.split('/')[-1]
        if file_path == target_code:
            # use temp file for processing
            target_code = 'claimed_' + target_code
        # Copy file to current working directory
        shutil.copy(file_path, target_code)
        command = 'Rscript'
        working_dir = '/home/docker/'
    else:
        raise NotImplementedError('Please provide a file_path to a jupyter notebook, python script, or R script.')

    if target_code.endswith('.py'):
        # Add code for logging and cli parameters to the beginning of the script
        with open(target_code, 'r') as f:
            script = f.read()
        script = python_component_setup_code + script
        with open(target_code, 'w') as f:
            f.write(script)

        # getting parameter from the script
        script_data = Pythonscript(target_code)
        dockerfile_template = custom_dockerfile_template or python_dockerfile_template

    elif target_code.lower().endswith('.r'):
        # Add code for logging and cli parameters to the beginning of the script
        with open(target_code, 'r') as f:
            script = f.read()
        script = r_component_setup_code + script
        with open(target_code, 'w') as f:
            f.write(script)
        # getting parameter from the script
        script_data = Rscript(target_code)
        dockerfile_template = custom_dockerfile_template or r_dockerfile_template
    else:
        raise NotImplementedError('C3 currently only supports jupyter notebooks, python scripts, and R scripts.')

    name = script_data.get_name()
    # convert description into a string with a single line
    description = ('"' + script_data.get_description().replace('\n', ' ').replace('"', '\'') +
                   ' – CLAIMED ' + CLAIMED_VERSION + '"')
    inputs = script_data.get_inputs()
    outputs = script_data.get_outputs()
    requirements = script_data.get_requirements()
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

    create_dockerfile(dockerfile_template, requirements, target_code, additional_files_path, working_dir, command)

    if version is None:
        # auto increase version based on registered images
        version = get_image_version(repository, name)

    logging.info(f'Building container image claimed-{name}:{version}')
    try:
        # Run docker build
        subprocess.run(
            f"docker build --platform linux/amd64 -t claimed-{name}:{version} . {'--no-cache' if no_cache else ''}",
            stdout=None if log_level == 'DEBUG' else subprocess.PIPE, check=True, shell=True
        )

        # Run docker tag
        logging.debug(f'Tagging images with "latest" and "{version}"')
        subprocess.run(
            f"docker tag claimed-{name}:{version} {repository}/claimed-{name}:{version}",
            stdout=None if log_level == 'DEBUG' else subprocess.PIPE, check=True, shell=True,
        )
        subprocess.run(
            f"docker tag claimed-{name}:{version} {repository}/claimed-{name}:latest",
            stdout=None if log_level == 'DEBUG' else subprocess.PIPE, check=True, shell=True,
        )
    except Exception as err:
        remove_temporary_files(file_path, target_code, additional_files_path)
        raise err
    logging.info('Successfully built image')

    logging.info(f'Pushing images to registry {repository}')
    try:
        # Run docker push
        subprocess.run(
            f"docker push {repository}/claimed-{name}:latest",
            stdout=None if log_level == 'DEBUG' else subprocess.PIPE, check=True, shell=True,
        )
        subprocess.run(
            f"docker push {repository}/claimed-{name}:{version}",
            stdout=None if log_level == 'DEBUG' else subprocess.PIPE, check=True, shell=True,
        )
        logging.info('Successfully pushed image to registry')
    except Exception as err:
        logging.error(f'Could not push images to namespace {repository}. '
                      f'Please check if docker is logged in or select a namespace with access.')
        if test_mode:
            logging.info('Continue processing (test mode).')
            pass
        else:
            remove_temporary_files(file_path, target_code, additional_files_path)
            raise err

    # Create application scripts
    create_kfp_component(name, description, repository, version, command, target_code, file_path, inputs, outputs)

    create_kubernetes_job(name, repository, version, target_code, command, working_dir, file_path, inputs)

    create_cwl_component(name, repository, version, file_path, inputs, outputs)

    print_claimed_command(name, repository, version, inputs)

    # Remove temp files
    remove_temporary_files(file_path, target_code, additional_files_path)


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
    parser.add_argument('--no-cache', action='store_true')
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
            custom_dockerfile_template = Template(f.read())
    else:
        custom_dockerfile_template = None

    create_operator(
        file_path=args.FILE_PATH,
        repository=args.repository,
        version=args.version,
        custom_dockerfile_template=custom_dockerfile_template,
        additional_files=args.ADDITIONAL_FILES,
        log_level=args.log_level,
        test_mode=args.test_mode,
        no_cache=args.no_cache,
    )


if __name__ == '__main__':
    main()
