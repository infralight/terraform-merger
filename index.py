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
    HARD_REFRESH = get_env_or_default("HARD_REFRESH", False)
    OUTPUT_DELIMITER = get_env_or_default("OUTPUT_DELIMITER", "output")
    EXCLUDED_ROOT_PATHS = get_env_or_default("EXCLUDED_ROOT_PREFIXES", None)

    ''' .tfstate files in S3 Bucket '''
    input_keys = s3_client.get_s3_keys_by_paths(INPUT_BUCKET, EXCLUDED_ROOT_PATHS, TERRAFORM_STATE_FILE_SUFFIX)

    ''' InfraLight merger latest state '''
    current_state_input_keys = s3_client.get_json_object_or_default(OUTPUT_BUCKET, INFRALIGHT_OUTPUT_STATE_PATH, [])

    ''' check if state files changed since last state '''
    if bool(HARD_REFRESH):
        diff_keys = current_state_input_keys
    else:
        diff_keys = [k for k in input_keys if k not in current_state_input_keys]
    if len(diff_keys) == 0:
        return "No Diff"

    ''' merge all state files '''
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

    ''' Saving merged state in OUTPUT s3 bucket '''
    output_key = os.path.join(OUTPUT_DELIMITER, "terraform_merged.tfstate")
    s3_client.put_object(OUTPUT_BUCKET, output_key, json.dumps(merged_state_file))

    ''' Saving merged state file InfraLight merger latest state '''
    s3_client.put_object(OUTPUT_BUCKET, INFRALIGHT_OUTPUT_STATE_PATH, json.dumps(input_keys))

    return "Done"