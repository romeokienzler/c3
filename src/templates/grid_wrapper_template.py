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

# import component code
from ${component_name} import *


# File with batches. Provided as a comma-separated list of strings or keys in a json dict.
gw_batch_file = os.environ.get('gw_batch_file', None)
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
# timeout in seconds to remove lock file from struggling job (default 1 hour)
gw_lock_timeout = int(os.environ.get('gw_lock_timeout', 3600))

# component interface
${component_interface}

def load_batches_from_file(batch_file):
    if batch_file.endswith('.json'):
        # load batches from keys of a json file
        logging.info(f'Loading batches from json file: {batch_file}')
        with open(batch_file, 'r') as f:
            batch_dict = json.load(f)
        batches = batch_dict.keys()

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
        all_files.extend(glob.glob(file_path_pattern.strip()))
    assert len(all_files) > 0, f"Found no files with file_path_patterns {file_path_patterns}."

    # get batches by applying the group by function to all file paths
    for path_string in all_files:
        exec('part = path_string' + group_by)
        batches.add(part)

    logging.info(f'Identified {len(batches)} batches')
    logging.debug(f'List of batches: {batches}')
    assert len(all_files) > 0, (f"Found batches with group_by {group_by}. "
                                f"Identified {len(all_files)} files, e.g., {all_files[:10]}.")
    return batches


def perform_process(process, batch):
    logging.debug(f'Check coordinator files for batch {batch}.')
    # init coordinator files
    lock_file = Path(gw_coordinator_path) / (batch + gw_lock_file_suffix)
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

    logging.debug(f'Locking batch {batch}.')
    lock_file.touch()

    # processing files with custom process
    logging.info(f'Processing batch {batch}.')
    try:
        target_files = process(batch, ${component_inputs})
    except Exception as e:
        # Remove lock file before raising the error
        lock_file.unlink()
        raise e

    # optional verify target files
    if target_files is not None:
        if isinstance(target_files, str):
            target_files = [target_files]
        for target_file in target_files:
            assert os.path.exists(target_file), f'Target file {target_file} does not exist for batch {batch}.'
    else:
        logging.info(f'Cannot verify batch {batch} (target files not provided).')

    logging.info(f'Finished Batch {batch}.')
    processed_file.touch()

    # Remove lock file
    lock_file.unlink()


def process_wrapper(sub_process, pre_process=None, post_process=None):
    delay = random.randint(1, 60)
    logging.info(f'Staggering start, waiting for {delay} seconds')
    time.sleep(delay)

    # Init coordinator dir
    Path(gw_coordinator_path).mkdir(exist_ok=True, parents=True)

    # run preprocessing
    if pre_process is not None:
        perform_process(pre_process, 'preprocess')

        # wait until preprocessing is finished
        processed_file = Path(gw_coordinator_path) / ('preprocess' + gw_processed_file_suffix)
        while not processed_file.exists():
            logging.info(f'Waiting for preprocessing to finish.')
            time.sleep(60)

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

    # Check if all batches are processed
    processed_status = [(Path(gw_coordinator_path) / (batch + gw_processed_file_suffix)).exists() for batch in batches]
    lock_status = [(Path(gw_coordinator_path) / (batch + gw_lock_file_suffix)).exists() for batch in batches]
    if all(processed_status):
        if post_process is not None:
            # run postprocessing
            perform_process(post_process, 'postprocess')

        logging.info('Finished all processes.')
    else:
        logging.info(f'Finished current process. Status batches: '
                     f'{sum(processed_status)} processed / {sum(lock_status)} locked / {len(processed_status)} total')


if __name__ == '__main__':
    process_wrapper(${component_process}, ${component_pre_process}, ${component_post_process})
