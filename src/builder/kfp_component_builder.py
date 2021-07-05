from kfp_component import  KfpComponent
from notebook import Notebook

nb = Notebook('../../test/notebooks/a_notebook.ipynb')
kfp = KfpComponent(nb)