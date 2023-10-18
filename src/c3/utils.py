import os
import logging
import json
import subprocess


def convert_notebook(path):
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
        elif cell['cell_type'] == 'code':
            for line in cell['source']:
                if line.strip().startswith('!'):
                    # convert sh scripts
                    if line.strip().startswith('!pip'):
                        # change pip install to comment
                        code_lines.append(line.replace('!pip', '# pip', 1))
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


def get_image_version(repository, name):
    """
    Get current version of the image from the registry and increase the version by 1.
    Default to 0.1.1 if no image is found in the registry.
    """
    logging.debug(f'Get image version from registry.')
    # list images
    image_list = subprocess.run(
        ['docker', 'image', 'ls', f'{repository}/claimed-{name}'],
        stdout=subprocess.PIPE
    ).stdout.decode('utf-8')
    # get list of image tags
    image_tags = [line.split()[1] for line in image_list.splitlines()][1:]
    # filter latest and none
    image_tags = [t for t in image_tags if t not in ['latest', '<none>']]
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
