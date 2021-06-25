from notebook import Notebook

nb = Notebook('../../test/notebooks/a_notebook.ipynb')

assert 'input_hmp' == nb.get_name()
assert 'This notebook pulls the HMP accelerometer sensor data classification data set' == nb.get_description()
inputs = nb.get_inputs()
assert 'data_csv' in inputs
assert 'master' in inputs
assert 'master2' in inputs
assert 'data_dir' in inputs

assert 'data.csv' == inputs['data_csv']
assert 'local[*]' == inputs['master']
assert '../../data/' == inputs['data_dir']
outputs = nb.get_outputs()
assert not 'output_data' in inputs
assert 'output_data' in outputs
assert 'output_data2' in outputs
assert '/tmp/output.csv' == outputs['output_data']
assert 'data_dir' not in outputs



