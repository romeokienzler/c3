from notebook import Notebook
from kfp_component import KfpComponent
from kfp_component_builder import KfpComponentBuilder
import sys


def main():
    args = sys.argv[1:]
    input_path = args[0]
    output_path = args[1]
    kfpcb = KfpComponentBuilder(input_path)
    with open(output_path, "w") as output_file:
        output_file.write(kfpcb.get_yaml())


if __name__ == "__main__":
    main()

