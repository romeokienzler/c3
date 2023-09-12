# TODO: Rename the file to the desired operator name.
"""
# TODO: Update the description of the operator.
This is a template for an operator that read files from COS, processes them, and saves the results to COS.
You can create a container image and KubeFlow job with C3.
"""

# TODO: Update the required pip packages.
# pip install xarray s3fs

import os
import logging
import sys
import re
import s3fs
import xarray as xr

# TODO: Add the operator interface.
#  You can use os.environ["name"], os.getenv("name"), or os.environ.get("name").
#  The default type is string. You can also use int, float, and bool values with type casting.
#  Optionally, you can set a default value like in the following.
# string example description with default value
string_example = os.getenv('string_example', 'default_value')
# int example description
int_example = int(os.getenv('int_example', 10))
# float example description
float_example = float(os.getenv('float_example', 0.1))
# bool example description
bool_example = bool(os.getenv('bool_example', False))

# # # Exemplary interface for processing COS files # # #

# glob pattern for all zarr files to process (e.g. path/to/files/**/*.zarr)
file_path_pattern = os.getenv('file_path_pattern')
# directory for the output files
target_dir = os.getenv('target_dir')
# access_key_id
access_key_id = os.getenv('access_key_id')
# secret_access_key
secret_access_key = os.getenv('secret_access_key')
# endpoint
endpoint = os.getenv('endpoint')
# bucket
bucket = os.getenv('bucket')
# set log level
log_level = os.getenv('log_level', "INFO")

# Init logging
root = logging.getLogger()
root.setLevel(log_level)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(log_level)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

logging.basicConfig(level=logging.CRITICAL)

# get arguments from the command (C3 passes all arguments in the form '<argument_name>=<value>')
parameters = list(
    map(lambda s: re.sub('$', '"', s),
        map(
            lambda s: s.replace('=', '="'),
            filter(
                lambda s: s.find('=') > -1 and bool(re.match(r'[A-Za-z0-9_]*=[.\/A-Za-z0-9]*', s)),
                sys.argv
            )
        )))

# set values from command arguments
for parameter in parameters:
    logging.info('Parameter: ' + parameter)
    exec(parameter)

# TODO: You might want to add type casting after the exec(parameter).
#  C3 will added this automatically in the future, but it not implemented yet.
# type casting
int_example = int(int_example)
float_example = float(float_example)
bool_example = bool(bool_example)


# TODO: Add your code.
#  You can just call a function from an additional file (must be in the same directory) or add your code here.
# Example code for processing COS files based on a file pattern
def main():
    # init s3
    s3 = s3fs.S3FileSystem(
        anon=False,
        key=access_key_id,
        secret=secret_access_key,
        client_kwargs={'endpoint_url': endpoint})

    # get file paths from a glob pattern, e.g., path/to/files/**/*.zarr
    file_paths = s3.glob(os.path.join(bucket, file_path_pattern))

    for file_path in file_paths:
        # open a zarr file from COS as xarray dataset
        ds = xr.open_zarr(s3fs.S3Map(root=f's3://{file_path}', s3=s3))

        # TODO: do something with the dataset
        processed_ds = ds

        # write processed dataset to s3
        # TODO: edit how to save the processed data
        target_path = os.path.join(bucket, target_dir, os.path.basename(file_path))
        processed_ds.to_zarr(s3fs.S3Map(root=f's3://{target_path}', s3=s3))


if __name__ == '__main__':
    main()
