import json
import logging
import os
import re
from c3.parser import ContentParser


class Pythonscript:
    def __init__(self, path, function_name: str = None):

        self.path = path
        with open(path, 'r') as f:
            self.script = f.read()

        self.name = os.path.basename(path)[:-3].replace('_', '-')
        assert '"""' in self.script, 'Please provide a description of the operator in the first doc string.'
        self.description = self.script.split('"""')[1].strip()
        self.envs = self._get_env_vars()

    def _get_env_vars(self):
        cp = ContentParser()
        env_names = cp.parse(self.path)['env_vars']
        return_value = dict()
        for env_name in env_names:
            comment_line = str()
            for line in self.script.split('\n'):
                if re.search("[\"']" + env_name + "[\"']", line):
                    # Check the description for current variable
                    if not comment_line.strip().startswith('#'):
                        # previous line was no description, reset comment_line.
                        comment_line = ''
                    if comment_line == '':
                        logging.info(f'Interface: No description for variable {env_name} provided.')
                    if re.search(r'=\s*int\(\s*os', line):
                        type = 'Integer'
                    elif re.search(r'=\s*float\(\s*os', line):
                        type = 'Float'
                    elif re.search(r'=\s*bool\(\s*os', line):
                        type = 'Boolean'
                    else:
                        type = 'String'
                    # get default value
                    if re.search(r"\(.*,.*\)", line):
                        # extract int, float, bool
                        default = re.search(r",\s*(.*?)\s*\)", line).group(1)
                        if type == 'String' and default != 'None':
                            # Process string default value
                            default = default[1:-1].replace("\"", "\'")
                    else:
                        default = None
                    return_value[env_name] = {
                        'description': comment_line.replace('#', '').replace("\"", "\'").strip(),
                        'type': type,
                        'default': default
                    }
                    break
                comment_line = line
        return return_value

    def get_requirements(self):
        requirements = []
        for line in self.script.split('\n'):
            pattern = r"([ ]*pip[ ]*install[ ]*)([A-Za-z=0-9.\-: ]*)"
            result = re.findall(pattern, line)
            if len(result) == 1:
                requirements.append((result[0][0].strip() + ' ' + result[0][1].strip()))
        return requirements

    def get_name(self):
        return self.name

    def get_description(self):
        return self.description

    def get_inputs(self):
        return {key: value for (key, value) in self.envs.items() if not key.startswith('output_')}

    def get_outputs(self):
        return {key: value for (key, value) in self.envs.items() if key.startswith('output_')}
