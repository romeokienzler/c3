from kfp_component import  KfpComponent
from notebook import Notebook
from string import Template
from io import StringIO


class KfpComponentBuilder():
    def __init__(self, notebook_url : str):
        nb = Notebook('../../test/notebooks/a_notebook.ipynb')
        self.kfp = KfpComponent(nb)

    def get_inputs(self):
        with StringIO() as inputs_str:
            for input in self.kfp.get_inputs():
                t = Template("- {name: $name, type: String, description: 'not yet supported'}")
                print(t.substitute(name=input), file=inputs_str)
            return inputs_str.getvalue()

    def get_outputs(self):
        with StringIO() as outputs_str:
            for output in self.kfp.get_outputs():
                t = Template("- {name: $name, type: String, description: 'not yet supported'}")
                print(t.substitute(name=output), file=outputs_str)
            return outputs_str.getvalue()

    def get_yaml(self):
        t = Template('''
name: $name
description: $description

inputs:
$inputs

outputs:
$outputs

implementation:
    container:
        image: $container_uri
        command: [
            seq 100
        ]
        ''')
        return t.substitute(
            name=self.kfp.get_name(),
            description=self.kfp.get_description(),
            inputs=self.get_inputs(),
            outputs=self.get_outputs(),
            container_uri=self.kfp.get_container_uri()
            )
