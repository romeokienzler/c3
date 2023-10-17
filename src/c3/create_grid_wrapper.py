import logging
import os
import argparse
import sys
from string import Template
from pythonscript import Pythonscript
from utils import convert_notebook
from create_operator import create_operator
from templates import grid_wrapper_template, cos_grid_wrapper_template, gw_component_setup_code, dockerfile_template


def wrap_component(component_path,
                   component_description,
                   component_dependencies,
                   component_interface,
                   component_inputs,
                   component_process,
                   cos,
                   ):
    # get component name from path
    component_name = os.path.splitext(os.path.basename(component_path))[0]

    gw_template = cos_grid_wrapper_template if cos else grid_wrapper_template
    grid_wrapper_code = gw_template.substitute(
        component_name=component_name,
        component_description=component_description,
        component_dependencies=component_dependencies,
        component_inputs=component_inputs,
        component_interface=component_interface,
        component_process=component_process,
    )

    # Write edited code to file
    grid_wrapper_file = f'cgw_{component_name}.py' if cos else f'gw_{component_name}.py'
    grid_wrapper_file_path = os.path.join(os.path.dirname(component_path), grid_wrapper_file)
    # remove 'component_' from gw path
    grid_wrapper_file_path = grid_wrapper_file_path.replace('component_', '')
    with open(grid_wrapper_file_path, 'w') as f:
        f.write(grid_wrapper_code)

    logging.info(f'Saved wrapped component to {grid_wrapper_file_path}')

    return grid_wrapper_file_path


def get_component_elements(file_path):
    # get required elements from component code
    py = Pythonscript(file_path)
    # convert description into a string with a single line
    description = (py.get_description().replace('\n', ' ').replace('"', '\''))
    inputs = py.get_inputs()
    outputs = py.get_outputs()
    dependencies = py.get_requirements()

    # combine inputs and outputs
    interface_values = {}
    interface_values.update(inputs)
    interface_values.update(outputs)

    # combine dependencies list
    dependencies = '\n# '.join(dependencies)

    # generate interface code from inputs and outputs
    interface = ''
    type_to_func = {'String': '', 'Boolean': 'bool', 'Integer': 'int', 'Float': 'float'}
    for variable, d in interface_values.items():
        interface += f"# {d['description']}\n"
        interface += f"component_{variable} = {type_to_func[d['type']]}(os.getenv('{variable}', {d['default']}))\n"

    # generate kwargs for the subprocesses
    process_inputs = ', '.join([f'{i}=component_{i}' for i in inputs.keys()])
    # use log level from grid wrapper
    process_inputs = process_inputs.replace('component_log_level', 'log_level')

    return description, interface, process_inputs, dependencies


# Adding code
def edit_component_code(file_path):
    file_name = os.path.basename(file_path)
    if file_path.endswith('.ipynb'):
        logging.info('Convert notebook to python script')
        target_file = convert_notebook(file_path)
        file_path = target_file
        file_name = os.path.basename(file_path)
    else:
        # write edited code to different file
        target_file = os.path.join(os.path.dirname(file_path), 'component_' + file_name)

    target_file_name = os.path.basename(target_file)

    with open(file_path, 'r') as f:
        script = f.read()
    # Add code for logging and cli parameters to the beginning of the script
    script = gw_component_setup_code + script
    # replace old filename with new file name
    script = script.replace(file_name, target_file_name)
    with open(target_file, 'w') as f:
        f.write(script)

    if '__main__' not in script:
        logging.warning('No __main__ found in component code. Grid wrapper will import functions from component, '
                        'which can lead to unexpected behaviour without using __main__.')

    logging.info('Saved component python script in ' + target_file)

    return target_file


def apply_grid_wrapper(file_path, component_process, cos, *args, **kwargs):
    assert file_path.endswith('.py') or file_path.endswith('.ipynb'), \
        "Please provide a component file path to a python script or notebook."

    file_path = edit_component_code(file_path)

    description, interface, inputs, dependencies = get_component_elements(file_path)

    component_elements = dict(
        component_path=file_path,
        component_description=description,
        component_dependencies=dependencies,
        component_interface=interface,
        component_inputs=inputs,
        component_process=component_process
    )

    logging.debug('Wrap component with parameters:')
    for component, value in component_elements.items():
        logging.debug(component + ':\n' + str(value) + '\n')

    logging.info('Wrap component')
    grid_wrapper_file_path = wrap_component(cos=cos, **component_elements)
    return grid_wrapper_file_path, file_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file_path', type=str, required=True,
                        help='Path to python script or notebook')
    parser.add_argument('-p', '--component_process', type=str, required=True,
                        help='Name of the component sub process that is executed for each batch.')
    parser.add_argument('-cos', action=argparse.BooleanOptionalAction, default=False,
                        help='Creates a grid wrapper for processing COS files')
    parser.add_argument('-r', '--repository', type=str, default=None,
                        help='Container registry address, e.g. docker.io/<your_username>')
    parser.add_argument('-v', '--version', type=str, default=None,
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

    grid_wrapper_file_path, component_path = apply_grid_wrapper(**vars(args))

    if args.repository is not None:
        logging.info('Generate CLAIMED operator for grid wrapper')

        # Add component path and init file path to additional_files
        if args.additional_files is None:
            args.additional_files = component_path
        else:
            if args.additional_files.startswith('['):
                args.additional_files = f'{args.additional_files[:-1]},{component_path}]'
            else:
                args.additional_files = f'[{args.additional_files},{component_path}]'

        # Update dockerfile template if specified
        if args.dockerfile_template_path != '':
            logging.info(f'Uses custom dockerfile template from {args.dockerfile_template_path}')
            with open(args.dockerfile_template_path, 'r') as f:
                dockerfile_template = Template(f.read())

        create_operator(
            file_path=grid_wrapper_file_path,
            repository=args.repository,
            version=args.version,
            dockerfile_template=dockerfile_template,
            additional_files=args.additional_files
        )

        logging.info('Remove local component file')
        os.remove(component_path)
