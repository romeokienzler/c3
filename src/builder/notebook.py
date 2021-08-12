import json
import re
from parser import ContentParser

class Notebook():
    def __init__(self, path):
        with open(path) as json_file:
            self.notebook = json.load(json_file)
            self.name = self.notebook['cells'][0]['source'][0].replace('#', '').strip()
            self.description = self.notebook['cells'][1]['source'][0]
            self.envs = self._get_env_vars(path)
            self.requirements = self._get_requirements()

    def _get_env_vars(self, path):
        cp = ContentParser()
        env_names = cp.parse(path)['env_vars']
        return_value = dict()
        for env_name in env_names:
            comment_line = str()     
            for line in self.notebook['cells'][4]['source']:
                if re.search("[\"']" + env_name + "[\"']", line):
                    assert '#' in comment_line, "comment line didn't contain #"
                    if "int(" in line:
                        type = 'Integer'
                    elif "float(" in line:
                        type = 'Float'
                    else:
                        type = 'String'

                    return_value[env_name]=(comment_line.replace('#', '').strip(),type,None)
                comment_line = line
        return return_value



    def _get_requirements(self):
        for cell in self.notebook['cells']:
            cell_content = cell['source'][0]
            pattern = r"(![ ]*pip[ ]*install[ ]*)([A-Za-z=0-9.:]*)"

            #print(re.findall(pattern,cell_content)) # TODO romeo multiple matches not working

    def get_name(self):
        return self.name

    def get_description(self):
        return self.description

    def get_inputs(self):
        return { key:value for (key,value) in self.envs.items() if not key.startswith('output_') }

    def get_outputs(self):
        return { key:value for (key,value) in self.envs.items() if key.startswith('output_') }


