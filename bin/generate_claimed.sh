#!/bin/bash
for file in `find ../claimed/component-library/ -name "*.ipynb"`; do ./bin/generate_kfp_component.sh $file `echo $file |sed 's/.ipynb/.yaml/g'`; done