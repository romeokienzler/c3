#!/bin/bash
for file in `find ../claimed/component-library/ -name "*.yaml"`; do
    new_file=`echo $file|sed -s 's/..\/claimed\/component-library//'`
    component_name=${file##*/}
    component_name=`echo $component_name | sed -s 's/.yaml//'`
    printf '"%s": {\n      "location": {\n        "url": "https://raw.githubusercontent.com/IBM/claimed/master/component-library/%s"\n      },\n      "category": "kfp"\n    },\n' $component_name $new_file
done