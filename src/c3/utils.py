import os
import logging
import json
import re
import subprocess


def convert_notebook(path):
    # TODO: switch to nbconvert long-term (need to replace pip install)
    with open(path) as json_file:
        notebook = json.load(json_file)

    # backwards compatibility
    if notebook['cells'][0]['cell_type'] == 'markdown' and notebook['cells'][1]['cell_type'] == 'markdown':
        logging.info('Merge first two markdown cells. File name is used as operator name, not first markdown cell.')
        notebook['cells'][1]['source'] = notebook['cells'][0]['source'] + ['\n'] + notebook['cells'][1]['source']
        notebook['cells'] = notebook['cells'][1:]

    code_lines = []
    for cell in notebook['cells']:
        if cell['cell_type'] == 'markdown':
            # add markdown as doc string
            code_lines.extend(['"""\n'] + [f'{line}' for line in cell['source']] + ['\n"""'])
        elif cell['cell_type'] == 'code' and cell['source'][0].startswith('%%bash'):
            code_lines.append('os.system("""')
            code_lines.extend(cell['source'][1:])
            code_lines.append('""")')
        elif cell['cell_type'] == 'code':
            for line in cell['source']:
                if line.strip().startswith('!'):
                    # convert sh scripts
                    if re.search('![ ]*pip', line):
                        # change pip install to comment
                        code_lines.append(re.sub('![ ]*pip', '# pip', line))
                    else:
                        # change sh command to os.system()
                        logging.info(f'Replace shell command with os.system() ({line})')
                        code_lines.append(line.replace('!', 'os.system(', 1).replace('\n', ')\n'))
                else:
                    # add code
                    code_lines.append(line)
        # add line break after cell
        code_lines.append('\n')
    code = ''.join(code_lines)

    py_path = path.split('/')[-1].replace('.ipynb', '.py')

    assert not os.path.exists(py_path), f"File {py_path} already exist. Cannot convert notebook."
    with open(py_path, 'w') as py_file:
        py_file.write(code)

    return py_path


def increase_image_version(last_version):
    try:
        # increase last version value by 1
        version = last_version.split('.')
        version[-1] = str(int(version[-1]) + 1)
        version = '.'.join(version)
    except:
        # fails if a string value was used for the last tag
        version = last_version + '.1'
        logging.debug(f'Failed to increase last value, adding .1')
        pass
    logging.info(f'Using version {version} based on latest tag ({last_version}).')
    return version


def pull_docker_image_tags(image):
    logging.warning("The current implementation can only query local docker images. "
                    "Please use an argument '-v <version>' to avoid duplicates.")
    # list images
    output = subprocess.run(
        ['docker', 'image', 'ls', image],
        stdout=subprocess.PIPE
    ).stdout.decode('utf-8')
    try:
        # remove header
        image_list = output.splitlines()[1:]
        # get list of image tags
        image_tags = [line.split()[1] for line in image_list]
    except:
        image_tags = []
        logging.error(f"Could not load image tags from 'docker image ls' output: {output}")
        pass

    # filter latest and none
    image_tags = [t for t in image_tags if t not in ['latest', '<none>']]
    return image_tags


def pull_icr_image_tags(image):
    # list images from icr
    output = subprocess.run(
        ['ibmcloud', 'cr', 'images', '--restrict', image.split('icr.io/', 1)[1]],
        stdout=subprocess.PIPE
    ).stdout.decode('utf-8')

    try:
        # remove header and final status
        image_list = output.splitlines()[3:-2]
        # get list of image tags
        image_tags = [line.split()[1] for line in image_list]
    except:
        image_tags = []
        logging.error(f"Could not load image tags from 'ibmcloud cr images' output: {output}")
        pass

    # filter latest and none
    image_tags = [t for t in image_tags if t not in ['latest', '<none>']]
    return image_tags


def get_image_version(repository, name):
    """
    Get current version of the image from the registry and increase the version by 1.
    Defaults to 0.1 if no image is found in the registry.
    """
    logging.debug(f'Get image version from registry.')
    if 'docker.io' in repository:
        logging.debug('Get image tags from docker.')
        image_tags = pull_docker_image_tags(f'{repository}/claimed-{name}')
    elif 'icr.io' in repository:
        logging.debug('Get image tags from ibmcloud container registry.')
        image_tags = pull_icr_image_tags(f'{repository}/claimed-{name}')
    else:
        logging.warning('Unrecognised container registry, using docker to query image tags.')
        image_tags = pull_docker_image_tags(f'{repository}/claimed-{name}')
    logging.debug(f'Image tags: {image_tags}')

    def check_only_numbers(test_str):
        return set(test_str) <= set('.0123456789')

    if len(image_tags) == 0:
        # default version
        version = '0.1'
        logging.info(f'Using default version {version}. No prior image tag found for {repository}/claimed-{name}.')

    elif not check_only_numbers(image_tags[0]):
        # increase last version
        version = increase_image_version(image_tags[0])
        logging.info(f'Using version {version} based on last version {image_tags[0]}.')

    else:
        # find the highest numerical version
        image_tags = list(filter(check_only_numbers, image_tags))
        image_tags.sort(key=lambda s: list(map(int, s.split('.'))))
        version = increase_image_version(image_tags[-1])
        logging.info(f'Using version {version} based on highest previous version {image_tags[-1]}.')

    return version
