from notebook import Notebook
from kfp_component import KfpComponent

nb = Notebook('../../test/notebooks/a_notebook.ipynb')
kfp = KfpComponent(nb)
assert 'input_hmp' == kfp.get_name()
assert 'This notebook pulls the HMP accelerometer sensor data classification data set' == kfp.get_description()
inputs = kfp.get_inputs()
assert 'data_csv' in inputs
assert 'master' in inputs
assert 'master2' in inputs
assert 'data_dir' in inputs
assert 'continuumio/anaconda3:2020.07' == kfp.get_container_uri()
assert 'data.csv' == inputs['data_csv']
assert 'local[*]' == inputs['master']
assert '../../data/' == inputs['data_dir']
outputs = kfp.get_outputs()
assert not 'output_data' in inputs
assert 'output_data' in outputs
assert 'output_data2' in outputs
assert '/tmp/output.csv' == outputs['output_data']
assert 'data_dir' not in outputs



