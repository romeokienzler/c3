import json
from parser import ContentParser

class Notebook():
    def __init__(self, path):
        with open(path) as json_file:
            notebook = json.load(json_file)
            self.name = notebook['cells'][0]['source'][0]
            self.description = notebook['cells'][1]['source'][0]

            cp = ContentParser()
            self.envs = cp.parse(path)['env_vars']

