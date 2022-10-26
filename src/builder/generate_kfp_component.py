from notebook import Notebook
from kfp_component import KfpComponent
from kfp_component_builder import KfpComponentBuilder
import sys


def main():
    args = sys.argv[1:]
    if len(args) < 4:
        print('Usage: input_path output_path source_uri(URI to the component source code to be downloaded) source_file_name(file name to be executed)')
        exit(-1)
    input_path = args[0]
    output_path = args[1]
    source_uri = args[2] # URI to the component source code to be downloaded
    source_file_name = args[3] # file name to be executed
    kfpcb = KfpComponentBuilder(input_path,source_uri,source_file_name)
    with open(output_path, "w") as output_file:
        output_file.write(kfpcb.get_yaml())


if __name__ == "__main__":
    main()

