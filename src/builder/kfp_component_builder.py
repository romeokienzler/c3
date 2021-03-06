from kfp_component import  KfpComponent
from notebook import Notebook
from string import Template
from io import StringIO


class KfpComponentBuilder():
    def __init__(self, notebook_url : str, source_uri : str, source_file_name : str):
        nb = Notebook(notebook_url)
        self.source_uri = source_uri
        self.source_file_name = source_file_name
        self.kfp = KfpComponent(nb)

    def get_inputs(self):
        with StringIO() as inputs_str:
            for input_key, input_value in self.kfp.get_inputs().items():
                t = Template("- {name: $name, type: $type, description: '$description'}")
                print(t.substitute(name=input_key, type=input_value[1], description=input_value[0]), file=inputs_str)
            return inputs_str.getvalue()

    def get_input_for_implementation(self):
        with StringIO() as inputs_str:
            for input_key, input_value in self.kfp.get_inputs().items():
                t = Template("        - {inputValue: $name}")
                print(t.substitute(name=input_key), file=inputs_str)
            return inputs_str.getvalue()    

    def get_outputs(self):
        with StringIO() as outputs_str:
            assert len(self.kfp.get_outputs()) == 1, 'exactly one output currently supported: '+ str((len(self.kfp.get_outputs())))
            for output_key, output_value in self.kfp.get_outputs().items():
                t = Template("- {name: $name, type: $type, description: '$description'}")
                print(t.substitute(name=output_key, type=output_value[1], description=output_value[0]), file=outputs_str)
            return outputs_str.getvalue()

    def get_output_name(self):
        assert len(self.kfp.get_outputs()) == 1, 'exactly one output currently supported'
        for output_key, output_value in self.kfp.get_outputs().items():
            return output_key

    def get_parameter_list(self):
        return_value = str()
        index = 0
        for output_key, output_value in self.kfp.get_outputs().items():
            return_value = return_value + output_key + '="$' + str(index) + '" '
            index = index + 1
        for input_key, input_value in self.kfp.get_inputs().items():
            return_value = return_value + input_key + '="$' + str(index) + '" '
            index = index + 1
        return return_value                 

        

    def get_yaml(self):
        t = Template('''name: $name
description: $description

inputs:
$inputs

outputs:
$outputs

implementation:
    container:
        image: $container_uri
        command:
        - sh
        - -ec
        - |
          $mkdir
          wget $source_uri
          $call
        - {outputPath: $outputPath}
$input_for_implementation''')
        return t.substitute(
            name=self.kfp.get_name(),
            description=self.kfp.get_description(),
            inputs=self.get_inputs(),
            outputs=self.get_outputs(),
            container_uri=self.kfp.get_container_uri(),
            outputPath=self.get_output_name(),
            input_for_implementation=self.get_input_for_implementation(),
            mkdir="mkdir -p `echo $0 |sed -e 's/\/[a-zA-Z0-9]*$//'`",
            source_uri=self.source_uri,
            call='ipython ' + self.source_file_name + ' ' + self.get_parameter_list()
        )
