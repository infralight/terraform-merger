import json
import os
from exceptions.missing_argument_exception import MissingArgumentException
from connectors.s3_connector import S3Connector

s3_client = S3Connector()


def get_env_or_default(key: str, default_value):
    return default_value if os.environ.get(key) is None else os.environ.get(key)


def lambda_handler(event, context):
    if get_env_or_default("INPUT_BUCKET", "") == "":
        raise MissingArgumentException("INPUT_BUCKET is a mandatory argument")

    if get_env_or_default("OUTPUT_BUCKET", "") == "":
        raise MissingArgumentException("OUTPUT_BUCKET is a mandatory argument")

    INPUT_BUCKET = get_env_or_default("INPUT_BUCKET", None)
    OUTPUT_BUCKET = get_env_or_default("OUTPUT_BUCKET", None)
    TERRAFORM_STATE_FILE_SUFFIX = get_env_or_default("TERRAFORM_STATE_SUFFIX", ".tfstate")
    INFRALIGHT_OUTPUT_STATE_PATH = get_env_or_default("INFRALIGHT_STATE_PATH", "merger.infl")

    ''' .tfstate files in S3 Bucket '''
    input_keys = s3_client.get_all_s3_keys(INPUT_BUCKET, TERRAFORM_STATE_FILE_SUFFIX)

    ''' state files to merge '''
    states_to_merge = []
    for s3_file_key in input_keys:
        state_object = s3_client.get_json_object_or_default(INPUT_BUCKET, s3_file_key['Key'], {})
        if state_object != {}:
            for resource in state_object['resources']:
                resource['terraform_version'] = state_object['terraform_version']

            states_to_merge.append(state_object)

    ''' merging state objects by their resources '''
    merged_list = []
    for state_object in states_to_merge:
        merged_list.extend(state_object['resources'])

    merged_state_file = states_to_merge[0]
    merged_state_file['resources'] = merged_list

    ''' Saving merged state file '''
    s3_client.put_object(OUTPUT_BUCKET, INFRALIGHT_OUTPUT_STATE_PATH, json.dumps(merged_state_file))

    return "Done"