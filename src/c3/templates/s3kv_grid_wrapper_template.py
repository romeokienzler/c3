"""
${component_name} got wrapped by grid_wrapper, which wraps any CLAIMED component and implements the generic grid computing pattern https://romeokienzler.medium.com/the-generic-grid-computing-pattern-transforms-any-sequential-workflow-step-into-a-transient-grid-c7f3ca7459c8

CLAIMED component description: ${component_description}
"""

# component dependencies
# ${component_dependencies}

import os
import json
import random
import logging
import time
import glob
from pathlib import Path
import pandas as pd
import s3fs


# import component code
from ${component_name} import *


explode_connection_string(cs):
    if cs is None:
        return None
    if cs.startswith('cos') or cs.startswith('s3'):
        buffer=cs.split('://')[1]
        access_key_id=buffer.split('@')[0].split(':')[0]
        secret_access_key=buffer.split('@')[0].split(':')[1]
        endpoint=buffer.split('@')[1].split('/')[0]
        path='/'.join(buffer.split('@')[1].split('/')[1:])
        return (access_key_id, secret_access_key, endpoint, path)
    else:
        return (None, None, None, cs)
        # TODO consider cs as secret and grab connection string from kubernetes



# File with batches. Provided as a comma-separated list of strings,  keys in a json dict or single column CSV with 'filename' has header. Either local path as [cos|s3]://user:pw@endpoint/path
gw_batch_file = os.environ.get('gw_batch_file', None)
(gw_batch_file_access_key_id, gw_batch_secret_access_key, gw_batch_endpoint, gw_batch_file) = explode_connection_string(gw_batch_file):


# file path pattern like your/path/**/*.tif. Multiple patterns can be separated with commas. Is ignored if gw_batch_file is provided.
gw_file_path_pattern = os.environ.get('gw_file_path_pattern', None)
# pattern for grouping file paths into batches like ".split('.')[-1]". Is ignored if gw_batch_file is provided.
gw_group_by = os.environ.get('gw_group_by', None)
# path to grid wrapper coordinator directory
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

def load_batches_from_file(batch_file):
    if gw_batch_file_access_key_id is not None:
        s3source = s3fs.S3FileSystem(
            anon=False,
            key=gw_batch_file_access_key_id,
            secret=gw_batch_secret_access_key,
            client_kwargs={'endpoint_url': gw_batch_endpoint})


        if batch_file.endswith('.json'):
            # load batches from keys of a json file
            logging.info(f'Loading batches from json file: {batch_file}')
            with s3source.open(gw_batch_file, 'r') as f:
                batch_dict = json.load(f)
            batches = batch_dict.keys()

        elif batch_file.endswith('.csv'):
            # load batches from keys of a csv file
            logging.info(f'Loading batches from csv file: {batch_file}')
            s3source.get(batch_file, batch_file)
            df = pd.read_csv(batch_file, header='infer')
            batches = df['filename'].to_list()

        else:
            # Load batches from comma-separated txt file
            logging.info(f'Loading comma-separated batch strings from file: {batch_file}')
            with s3source.open(gw_batch_file, 'r') as f:
                batch_string = f.read()
            batches = [b.strip() for b in batch_string.split(',')]
    else:
        if batch_file.endswith('.json'):
            # load batches from keys of a json file
            logging.info(f'Loading batches from json file: {batch_file}')
            with open(batch_file, 'r') as f:
                batch_dict = json.load(f)
            batches = batch_dict.keys()

        elif batch_file.endswith('.csv'):
            # load batches from keys of a csv file
            logging.info(f'Loading batches from csv file: {batch_file}')
            df = pd.read_csv(batch_file, header='infer')
            batches = df['filename'].to_list()

        else:
            # Load batches from comma-separated txt file
            logging.info(f'Loading comma-separated batch strings from file: {batch_file}')
            with open(batch_file, 'r') as f:
                batch_string = f.read()
            batches = [b.strip() for b in batch_string.split(',')]

    logging.info(f'Loaded {len(batches)} batches')
    logging.debug(f'List of batches: {batches}')
    assert len(batches) > 0, f"batch_file {batch_file} has no batches."
    return batches


def identify_batches_from_pattern(file_path_patterns, group_by):
    logging.info(f'Start identifying files and batches')
    batches = set()
    all_files = []

    # Iterate over comma-separated paths
    for file_path_pattern in file_path_patterns.split(','):
        logging.info(f'Get file paths from pattern: {file_path_pattern}')
        files = glob.glob(file_path_pattern.strip())
        assert len(files) > 0, f"Found no files with file_path_pattern {file_path_pattern}."
        all_files.extend(files)

    # get batches by applying the group by function to all file paths
    for path_string in all_files:
        part = eval('str(path_string)' + group_by, {"group_by": group_by, "path_string": path_string})
        assert part != '', f'Could not extract batch with path_string {path_string} and group_by {group_by}'
        batches.add(part)

    logging.info(f'Identified {len(batches)} batches')
    logging.debug(f'List of batches: {batches}')

    return batches


def perform_process(process, batch):
    logging.debug(f'Check coordinator files for batch {batch}.')
    # init coordinator files
    lock_file = Path(gw_coordinator_path) / (batch + gw_lock_file_suffix)
    error_file = Path(gw_coordinator_path) / (batch + gw_error_file_suffix)
    processed_file = Path(gw_coordinator_path) / (batch + gw_processed_file_suffix)

    if lock_file.exists():
        # remove strugglers
        if lock_file.stat().st_mtime < time.time() - gw_lock_timeout:
            logging.debug(f'Lock file {lock_file} is expired.')
            lock_file.unlink()
        else:
            logging.debug(f'Batch {batch} is locked.')
            return

    if processed_file.exists():
        logging.debug(f'Batch {batch} is processed.')
        return

    if error_file.exists():
        if gw_ignore_error_files:
            logging.info(f'Ignoring previous error in batch {batch} and rerun.')
        else:
            logging.debug(f'Batch {batch} has error.')
            return

    logging.debug(f'Locking batch {batch}.')
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.touch()

    # processing files with custom process
    logging.info(f'Processing batch {batch}.')
    try:
        target_files = process(batch, ${component_inputs})
    except Exception as err:
        logging.error(f'{type(err).__name__} in batch {batch}: {err}')
        # Write error to file
        with open(error_file, 'w') as f:
            f.write(f"{type(err).__name__} in batch {batch}: {err}")
        lock_file.unlink()
        logging.error(f'Continue processing.')
        return

    # optional verify target files
    if target_files is not None:
        if isinstance(target_files, str):
            target_files = [target_files]
        for target_file in target_files:
            if not os.path.exists(target_file):
                logging.error(f'Target file {target_file} does not exist for batch {batch}.')
    else:
        logging.info(f'Cannot verify batch {batch} (target files not provided).')

    logging.info(f'Finished Batch {batch}.')
    processed_file.touch()

    # Remove lock file
    if lock_file.exists():
        lock_file.unlink()
    else:
        logging.warning(f'Lock file {lock_file} was removed by another process. '
                        f'Consider increasing gw_lock_timeout (currently {gw_lock_timeout}s) to repeated processing.')



def process_wrapper(sub_process):
    delay = random.randint(1, 60)
    logging.info(f'Staggering start, waiting for {delay} seconds')
    time.sleep(delay)

    # Init coordinator dir
    coordinator_dir = Path(gw_coordinator_path)
    coordinator_dir.mkdir(exist_ok=True, parents=True)

    # get batches
    if gw_batch_file is not None and os.path.isfile(gw_batch_file):
        batches = load_batches_from_file(gw_batch_file)
    elif gw_file_path_pattern is not None and gw_group_by is not None:
        batches = identify_batches_from_pattern(gw_file_path_pattern, gw_group_by)
    else:
        raise ValueError("Cannot identify batches. "
                         "Provide valid gw_batch_file or gw_file_path_pattern and gw_group_by.")

    # Iterate over all batches
    for batch in batches:
        perform_process(sub_process, batch)

    # Check and log status of batches
    processed_status = [(coordinator_dir / (batch + gw_processed_file_suffix)).exists() for batch in batches]
    lock_status = [(coordinator_dir / (batch + gw_lock_file_suffix)).exists() for batch in batches]
    error_status = [(coordinator_dir / (batch + gw_error_file_suffix)).exists() for batch in batches]

    logging.info(f'Finished current process. Status batches: '
                 f'{sum(processed_status)} processed / {sum(lock_status)} locked / {sum(error_status)} errors / {len(processed_status)} total')

    if sum(error_status):
        logging.error(f'Found errors! Resolve errors and rerun operator with gw_ignore_error_files=True.')
        # print all error messages
        for error_file in coordinator_dir.glob('**/*' + gw_error_file_suffix):
            with open(error_file, 'r') as f:
                logging.error(f.read())


if __name__ == '__main__':
    process_wrapper(${component_process}) 
