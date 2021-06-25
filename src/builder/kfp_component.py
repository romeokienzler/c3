from base_component_spec import BaseComponentSpec
from notebook import Notebook

class KfpComponent(BaseComponentSpec):
    def __init__(self, noteboook : Notebook):
        self.name = noteboook.get_name()
        self.description = noteboook.get_description()
        self.inputs = noteboook.get_inputs()
        self.outputs = noteboook.get_outputs()

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def get_container_uri(self) -> str:
        return 'continuumio/anaconda3:2020.07'

    def get_inputs(self):
        return self.inputs

    def get_outputs(self):
        return self.outputs
