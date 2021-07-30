from __future__ import print_function

import glob
import json
import os
import random
import re
import swagger_client
import tarfile
import tempfile

from io import BytesIO
from os import environ as env
from pprint import pprint
from swagger_client.api_client import ApiClient, Configuration
# Copyright 2021 IBM Corporation
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 
 
from swagger_client.models import ApiComponent, ApiGetTemplateResponse, ApiListComponentsResponse, \
    ApiGenerateCodeResponse, ApiRunCodeResponse
from swagger_client.rest import ApiException
from sys import stderr
from urllib3.response import HTTPResponse

host = env.get("MLX_API_SERVICE_HOST",'127.0.0.1')
port = env.get("MLX_API_SERVICE_PORT", '8080')


api_base_path = 'apis/v1alpha1'

def get_swagger_client():

    config = Configuration()
    config.host = f'http://{host}:{port}/{api_base_path}'
    api_client = ApiClient(configuration=config)

    return api_client

def create_tar_file(yamlfile_name):

    yamlfile_basename = os.path.basename(yamlfile_name)
    tmp_dir = tempfile.gettempdir()
    tarfile_path = os.path.join(tmp_dir, yamlfile_basename.replace(".yaml", ".tgz"))

    with tarfile.open(tarfile_path, "w:gz") as tar:
        tar.add(yamlfile_name, arcname=yamlfile_basename)

    tar.close()

    return tarfile_path

def upload_component_file(component_id, file_path):

    api_client = get_swagger_client()
    api_instance = swagger_client.ComponentServiceApi(api_client=api_client)

    try:
        response = api_instance.upload_component_file(id=component_id, uploadfile=file_path)
        print(f"Upload file '{file_path}' to component with ID '{component_id}'")

    except ApiException as e:
        print("Exception when calling ComponentServiceApi -> upload_component_file: %s\n" % e, file=stderr)
        raise e

def main():
    
    component_file = create_tar_file('../../test_component.yaml')
    upload_component_file('test4',component_file)

if __name__ == '__main__':
    main()