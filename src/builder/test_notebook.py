from notebook import Notebook

nb = Notebook('../../test/notebooks/a_notebook.ipynb')
print(nb.name)
print(nb.description)
print(nb.envs)
print(nb.requirements)