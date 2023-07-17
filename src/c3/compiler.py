import subprocess

def main():
    try:
        #output = subprocess.check_output('pwd', shell=True, universal_newlines=True)
        output = subprocess.check_output('ipython generate_kfp_component.ipynb', shell=True, universal_newlines=True)
        print(output)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")


if __name__ == "__main__":
    main()