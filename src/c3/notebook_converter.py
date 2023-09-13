
import json
import logging
import os


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
