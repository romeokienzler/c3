source ./venv/bin/activate
cd src/builder
python ./test_kfp_component.py
python ./test_notebook.py
python ./test_kfp_component_builder.py