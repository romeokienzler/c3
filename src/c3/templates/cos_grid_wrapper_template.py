"""
${component_name} got wrapped by cos_grid_wrapper, which wraps any CLAIMED component and implements the generic grid computing pattern for cos files https://romeokienzler.medium.com/the-generic-grid-computing-pattern-transforms-any-sequential-workflow-step-into-a-transient-grid-c7f3ca7459c8

CLAIMED component description: ${component_description}
"""

# pip install s3fs
# component dependencies
# ${component_dependencies}

import os
import json
import random
import logging
import shutil
import time
import glob
import s3fs
from datetime import datetime
from pathlib import Path

# import component code
from ${component_name} import *


# File containing batches. Provided as a comma-separated list of strings or keys in a json dict. All batch file names must contain the batch name.
gw_batch_file = os.environ.get('gw_batch_file', None)
# file path pattern like your/path/**/*.tif. Multiple patterns can be separated with commas. It is ignored if gw_batch_file is provided.
gw_file_path_pattern = os.environ.get('gw_file_path_pattern', None)
# pattern for grouping file paths into batches like ".split('.')[-2]". It is ignored if gw_batch_file is provided.
gw_group_by = os.environ.get('gw_group_by', None)

# comma-separated list of additional cos files to copy
gw_additional_source_files = os.environ.get('gw_additional_source_files', '')
# download source cos files to local input path
gw_local_input_path = os.environ.get('gw_local_input_path', 'input')
# upload local target files to target cos path
gw_local_target_path = os.environ.get('gw_local_target_path', 'target')

# cos source_access_key_id
gw_source_access_key_id = os.environ.get('gw_source_access_key_id')
# cos source_secret_access_key
gw_source_secret_access_key = os.environ.get('gw_source_secret_access_key')
# cos source_endpoint
gw_source_endpoint = os.environ.get('gw_source_endpoint')
# cos source_bucket
gw_source_bucket = os.environ.get('gw_source_bucket')

# cos target_access_key_id (uses source s3 if not provided)
gw_target_access_key_id = os.environ.get('gw_target_access_key_id', None)
# cos target_secret_access_key (uses source s3 if not provided)
gw_target_secret_access_key = os.environ.get('gw_target_secret_access_key', None)
# cos target_endpoint (uses source s3 if not provided)
gw_target_endpoint = os.environ.get('gw_target_endpoint', None)
# cos target_bucket (uses source s3 if not provided)
gw_target_bucket = os.environ.get('gw_target_bucket', None)
# cos target_path
gw_target_path = os.environ.get('gw_target_path')

# cos coordinator_access_key_id (uses source s3 if not provided)
gw_coordinator_access_key_id = os.environ.get('gw_coordinator_access_key_id', None)
# cos coordinator_secret_access_key (uses source s3 if not provided)
gw_coordinator_secret_access_key = os.environ.get('gw_coordinator_secret_access_key', None)
# cos coordinator_endpoint (uses source s3 if not provided)
gw_coordinator_endpoint = os.environ.get('gw_coordinator_endpoint', None)
# cos coordinator_bucket (uses source s3 if not provided)
gw_coordinator_bucket = os.environ.get('gw_coordinator_bucket', None)
# cos path to grid wrapper coordinator directory
gw_coordinator_path = os.environ.get('gw_coordinator_path')
# lock file suffix
gw_lock_file_suffix = os.environ.get('gw_lock_file_suffix', '.lock')
# processed file suffix
gw_processed_file_suffix = os.environ.get('gw_lock_file_suffix', '.processed')
# error file suffix
gw_error_file_suffix = os.environ.get('gw_error_file_suffix', '.err')
# timeout in seconds to remove lock file from struggling job (default 3 hours)
gw_lock_timeout = int(os.environ.get('gw_lock_timeout', 10800))
# ignore error files and rerun batches with errors
gw_ignore_error_files = bool(os.environ.get('gw_ignore_error_files', False))


# component interface
${component_interface}

# init s3
s3source = s3fs.S3FileSystem(
    anon=False,
    key=gw_source_access_key_id,
    secret=gw_source_secret_access_key,
    client_kwargs={'endpoint_url': gw_source_endpoint})

if gw_target_endpoint is not None:
    s3target = s3fs.S3FileSystem(
        anon=False,
        key=gw_target_access_key_id,
        secret=gw_target_secret_access_key,
        client_kwargs={'endpoint_url': gw_target_endpoint})
else:
    logging.debug('Using source bucket as target bucket.')
    gw_target_bucket = gw_source_bucket
    s3target = s3source

if gw_coordinator_bucket is not None:
    s3coordinator = s3fs.S3FileSystem(
        anon=False,
        key=gw_coordinator_access_key_id,
        secret=gw_coordinator_secret_access_key,
        client_kwargs={'endpoint_url': gw_coordinator_endpoint})
else:
    logging.debug('Using source bucket as coordinator bucket.')
    gw_coordinator_bucket = gw_source_bucket
    s3coordinator = s3source

def load_batches_from_file(batch_file):
    if batch_file.endswith('.json'):
        # load batches from keys of a json file
        logging.info(f'Loading batches from json file: {batch_file}')
        with s3source.open(Path(gw_source_bucket) / batch_file, 'r') as f:
            batch_dict = json.load(f)
        batches = batch_dict.keys()

    else:
        # Load batches from comma-separated txt file
        logging.info(f'Loading comma-separated batch strings from file: {batch_file}')
        with s3source.open(Path(gw_source_bucket) / batch_file, 'r') as f:
            batch_string = f.read()
        batches = [b.strip() for b in batch_string.split(',')]

    logging.info(f'Loaded {len(batches)} batches')
    logging.debug(f'List of batches: {batches}')
    assert len(batches) > 0, f"batch_file {batch_file} has no batches."
    return batches


def get_files_from_pattern(file_path_patterns):
    logging.info(f'Start identifying files')
    all_files = []

    # Iterate over comma-separated paths
    for file_path_pattern in file_path_patterns.split(','):
        logging.info(f'Get file paths from pattern: {file_path_pattern}')
        files = s3source.glob(str(Path(gw_source_bucket) / file_path_pattern.strip()))
        assert len(files) > 0, f"Found no files with file_path_pattern {file_path_pattern}."
        all_files.extend(files)
    logging.info(f'Found {len(all_files)} cos files')
    return all_files

def identify_batches_from_pattern(file_path_patterns, group_by):
    logging.info(f'Start identifying files and batches')
    batches = set()
    all_files = get_files_from_pattern(file_path_patterns)

    # get batches by applying the group by function to all file paths
    for path_string in all_files:
        part = eval('str(path_string)' + group_by, {"group_by": group_by, "path_string": path_string})
        assert part != '', f'Could not extract batch with path_string {path_string} and group_by {group_by}'
        batches.add(part)

    logging.info(f'Identified {len(batches)} batches')
    logging.debug(f'List of batches: {batches}')

    return batches, all_files


def perform_process(process, batch, cos_files):
    logging.debug(f'Check coordinator files for batch {batch}.')
    # init coordinator files
    coordinator_dir = Path(gw_coordinator_bucket) / gw_coordinator_path
    lock_file = str(coordinator_dir / (batch + gw_lock_file_suffix))
    processed_file = str(coordinator_dir / (batch + gw_processed_file_suffix))
    error_file = str(coordinator_dir / (batch + gw_error_file_suffix))

    if s3coordinator.exists(lock_file):
        # remove strugglers
        last_modified = s3coordinator.info(lock_file)['LastModified']
        if (datetime.now(last_modified.tzinfo) - last_modified).total_seconds() > gw_lock_timeout:
            logging.info(f'Lock file {lock_file} is expired.')
            s3coordinator.rm(lock_file)
        else:
            logging.debug(f'Batch {batch} is locked.')
            return

    if s3coordinator.exists(processed_file):
        logging.debug(f'Batch {batch} is processed.')
        return

    if s3coordinator.exists(error_file):
        if gw_ignore_error_files:
            logging.info(f'Ignoring previous error in batch {batch} and rerun.')
        else:
            logging.debug(f'Batch {batch} has error.')
            return

    logging.debug(f'Locking batch {batch}.')
    s3coordinator.touch(lock_file)
    logging.info(f'Processing batch {batch}.')

    # Create input and target directories
    input_path = Path(gw_local_input_path)
    target_path = Path(gw_local_target_path)
    assert not input_path.exists(), (f'gw_local_input_path ({gw_local_input_path}) already exists. '
                                     f'Please provide a new input path.')
    assert not target_path.exists(), (f'gw_local_target_path ({gw_local_target_path}) already exists. '
                                     f'Please provide a new target path.')
    input_path.mkdir(parents=True)
    target_path.mkdir(parents=True)

    # Download cos files to local input folder
    batch_fileset = list(filter(lambda file: batch in file, cos_files))
    if gw_additional_source_files != '':
        additional_source_files = [f.strip() for f in gw_additional_source_files.split(',')]
        batch_fileset.extend(additional_source_files)
    logging.info(f'Downloading {len(batch_fileset)} files from COS')
    for cos_file in batch_fileset:
        local_file = str(input_path / cos_file.split('/', 1)[-1])
        logging.debug(f'Downloading {cos_file} to {local_file}')
        s3source.get(cos_file, local_file)

    # processing files with custom process
    try:
        target_files = process(batch, ${component_inputs})
    except Exception as err:
        logging.error(f'{type(err).__name__} in batch {batch}: {err}')
        # Write error to file
        with s3coordinator.open(error_file, 'w') as f:
            f.write(f"{type(err).__name__} in batch {batch}: {err}")
        s3coordinator.rm(lock_file)
        logging.error(f'Continue processing.')
        return

    # optional verify target files
    if target_files is not None:
        if isinstance(target_files, str):
            target_files = [target_files]
        for target_file in target_files:
            if not os.path.exists(target_file):
                logging.error(f'Target file {target_file} does not exist for batch {batch}.')
        if any([not str(t).startswith(gw_local_target_path) for t in target_files]):
            logging.warning('Some target files are not in target path. Only files in target path are uploaded.')
    else:
        logging.info(f'Cannot verify batch {batch} (target files not provided). Using files in target_path.')

    # upload files in target path
    local_target_files = list(target_path.glob('*'))
    logging.info(f'Uploading {len(local_target_files)} target files to COS.')
    for local_file in local_target_files:
        cos_file = Path(gw_target_bucket) / gw_target_path / local_file.relative_to(target_path)
        logging.debug(f'Uploading {local_file} to {cos_file}')
        s3target.put(str(local_file), str(cos_file))

    logging.info(f'Remove local input and target files.')
    shutil.rmtree(input_path)
    shutil.rmtree(target_path)

    logging.info(f'Finished Batch {batch}.')
    s3coordinator.touch(processed_file)
    # Remove lock file
    if s3coordinator.exists(lock_file):
        s3coordinator.rm(lock_file)
    else:
        logging.warning(f'Lock file {lock_file} was removed by another process. '
                        f'Consider increasing gw_lock_timeout (currently {gw_lock_timeout}s) to repeated processing.')


def process_wrapper(sub_process):
    delay = random.randint(1, 60)
    logging.info(f'Staggering start, waiting for {delay} seconds')
    time.sleep(delay)

    # Init coordinator dir
    coordinator_dir = Path(gw_coordinator_bucket) / gw_coordinator_path
    s3coordinator.makedirs(coordinator_dir, exist_ok=True)

    # get batches
    if gw_batch_file is not None and os.path.isfile(gw_batch_file):
        batches = load_batches_from_file(gw_batch_file)
        cos_files = get_files_from_pattern(gw_file_path_pattern)
    elif gw_file_path_pattern is not None and gw_group_by is not None:
        batches, cos_files = identify_batches_from_pattern(gw_file_path_pattern, gw_group_by)
    else:
        raise ValueError("Cannot identify batches. "
                         "Provide valid gw_batch_file or gw_file_path_pattern and gw_group_by.")

    # Iterate over all batches
    for batch in batches:
        perform_process(sub_process, batch, cos_files)

    # Check and log status of batches
    processed_status = [s3coordinator.exists(coordinator_dir / (batch + gw_processed_file_suffix)) for batch in batches]
    lock_status = [s3coordinator.exists(coordinator_dir / (batch + gw_lock_file_suffix)) for batch in batches]
    error_status = [s3coordinator.exists(coordinator_dir / (batch + gw_error_file_suffix)) for batch in batches]

    logging.info(f'Finished current process. Status batches: '
                 f'{sum(processed_status)} processed / {sum(lock_status)} locked / {sum(error_status)} errors / {len(processed_status)} total')

    if sum(error_status):
        logging.error(f'Found errors! Resolve errors and rerun operator with gw_ignore_error_files=True.')
        # print all error messages
        for error_file in s3coordinator.glob(str(coordinator_dir / ('**/*' + gw_error_file_suffix))):
            with s3coordinator.open(error_file, 'r') as f:
                logging.error(f.read())


if __name__ == '__main__':
    process_wrapper(${component_process})
