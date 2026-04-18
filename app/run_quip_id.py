import argparse
import json
import os
from datetime import datetime
from glob import glob
from pathlib import Path
import requests
import time_gap_analysis
import ascvndlconvertor
import constants
import extractgzfiles
import functions
import jira
import logger_util
import process_results
import vndl_health_check
import pandas as pd
import column_names
import ecg_fnv_logic
from gcp_storage_utils import get_gcp_bucket
from process_results import ResultData
from status import Status, WakeEvents
import google
from google.auth import impersonated_credentials
from google.cloud import secretmanager
import time 
import vin_identification
from ign_off import extract_ign_off_run_time as ign_off_extract_ign_off_run_time
import ecg_log_parser


os.environ.update({
      "HTTP_PROXY": "http://internet.ford.com:83",
      "HTTPS_PROXY": "http://internet.ford.com:83",
      "NO_PROXY": "localhost,127.0.0.1,.ford.com,.local,.internal,.googleapis.com,19.0.0.0/8,136.1.0.0/16,10.0.0.0/8"
  })

# This function uploads files from a directory_path into dest_bucket_name
def upload_from_directory(directory_path: str, dest_bucket_name: str, dest_blob_prefix: str):
    try:
        rel_paths = glob(directory_path + '/**', recursive=True)
        bucket = get_gcp_bucket(dest_bucket_name)
        for local_file in rel_paths:
            remote_path = f'{dest_blob_prefix}{"/".join(local_file.split(os.sep)[1:])}'
            if os.path.isfile(local_file):
                blob = bucket.blob(remote_path)
                blob.upload_from_filename(local_file)
    except Exception as e:
        error_message = f"Error in upload_from_directory: {e}"
        logger_util.error(error_message, e, Status.UPLOAD_ERROR, directory_path)  # Log the error
        
        raise  # Re-raise the exception to halt further execution if needed

def preserve_processed_data(args, quip_data, logs):
    try:
        # Saving Quip data to file
        try:
            quip_file = f"{constants.PROCESSED_DATA_PATH + constants.job_tag}/{logger_util.LogUtil.quip_id}_quip_data.json"
            with open(quip_file, "w") as json_file:
                json_file.write(json.dumps(quip_data))
        except Exception as e:
            print(f"Failed to save data to {quip_file}, reason : {e}")
            error_message = f"Failed to save quip data to {quip_file}, reason : {e}"
            logger_util.error(error_message, e, Status.FILE_SAVE_ERROR, quip_file)
            

        # Saving logs to file
        try:
            log_file = f"{constants.PROCESSED_DATA_PATH + constants.job_tag}/{logger_util.LogUtil.quip_id}_logs.json"
            with open(log_file, "w") as json_file:
                json_file.write(json.dumps(logs))
        except Exception as e:
            print(f"Failed to save data to {quip_file}, reason {e}")
            error_message = f"Failed to save logs to {log_file}, reason {e}"
            logger_util.error(error_message, e, Status.FILE_SAVE_ERROR, log_file)
            

        upload_from_directory(constants.PROCESSED_DATA_PATH + constants.job_tag + "/",
                              args.gcs_bucket_input_quip,
                              dest_blob_prefix=args.gcs_bucket_prefix_quip + constants.PROCESSED_DATA_PATH)
    except Exception as e:
        error_message = f"Error in preserve_processed_data: {e}"
        logger_util.error(error_message, e, Status.PRESERVE_DATA_ERROR, constants.PROCESSED_DATA_PATH + constants.job_tag + "/")
        

# This function processes each quip event received in args_parser
def process_quip_event(args_parser):
    try:
        Path(constants.RESULT_PATH).mkdir(parents=True, exist_ok=True)
        Path(constants.PROCESSED_DATA_PATH).mkdir(parents=True, exist_ok=True)

        # Reading all arguments
        args_parser.add_argument('--quip_id', metavar='QUIP_ID')
        args_parser.add_argument('--data_date', metavar='DATA_DATE')
        args_parser.add_argument('--ecg_path', metavar='ECG_PATH')  
        args_parser.add_argument('--ram_dump', metavar='RAM_DUMP')
        args_parser.add_argument('--gcs_bucket_input_quip', metavar='GCP_CLOUD_STORAGE_BUCKET_INPUT_QUIP')
        args_parser.add_argument('--gcs_bucket_prefix_quip', metavar='GCP_CLOUD_STORAGE_BUCKET_PREFIX_QUIP')
        args_parser.add_argument('--gcs_bucket_prefix_input', metavar='GCP_CLOUD_STORAGE_BUCKET_PREFIX_INPUT')
        args_parser.add_argument('--gcs_bucket_prefix_result', metavar='GCP_CLOUD_STORAGE_BUCKET_PREFIX_RESULT')
        args = args_parser.parse_args()

        # Initializing logger util with processing quip_id so that it can be used while logging
        logger_util.LogUtil.quip_id = args.quip_id

        logger_util.info("QUIP Processing Started", Status.RUNQUIP_STARTED, "")
        logger_util.info(f"Args received : {args}", Status.RUNQUIP_STARTED, "")

        # Cleans QUIP files and results folders in the virtual machine
        functions.clean_path(Path(constants.QUIP_PATH))
        functions.clean_path(Path(constants.RESULT_PATH))
        functions.clean_path(Path(constants.PROCESSED_DATA_PATH))

        # download from GCS
        # add gcs self retry on each file while downloading
        bucket_prefix_quip = args.gcs_bucket_prefix_quip  # experiments/sheydari_test_running_pipeline/
        local_quip_magic_number = len(bucket_prefix_quip.split("/")) - 1
        bucket_input_quip = args.gcs_bucket_input_quip  # qed-battery-fnv-dev-000
        bucket_prefix_input = args.gcs_bucket_prefix_input  # experiments/sheydari_test_running_pipeline/QUIP_files/
        prefix = f'{bucket_prefix_input}{args.quip_id}/'

        bucket = get_gcp_bucket(bucket_name=bucket_input_quip)
        blobs = bucket.list_blobs(prefix=prefix)
        for blob in blobs:
            if blob.name.endswith("/"):
                continue
            file_split = blob.name.split("/")[local_quip_magic_number:]
            local_file_name = "/".join(file_split)  # getting filename from gcp path
            directory = "/".join(file_split[0:-1])  # getting directories for the above file
            Path(directory).mkdir(parents=True, exist_ok=True)  # creating directory path in VM
            blob.download_to_filename(local_file_name)  # copying file to the directory in VM

        process_results.ProcessPaths.root_directory = os.getcwd()
        functions.create_path_for_results()

        processing_quips = functions.get_quip_ids(args.quip_id)  # Fetching all quip ids and their children if any
        for key, value in processing_quips.items():
            # Clearing result data
            process_results.clear_result_data()

            # Moving to the src directory
            os.chdir(process_results.ProcessPaths.root_directory)

            # Processing quip event
            process_quip(args, key, value)

            # save results to big query
            quip_data, logs = process_results.prepare_quip_result_data()

            if quip_data is None:
                logger_util.info(f"Completed processing {args.quip_id}", Status.RESULTS_SAVING, '')
            else:
                logger_util.warning("Failed to insert data, saving results to a file", 'BigQuery insertion failed',
                                    Status.RESULTS_SAVING, '')
                error_message = f"Failed to insert data, saving results to a file"
                quip_id = f"{args.quip_id}"
                
                preserve_processed_data(args, quip_data, logs)
    except Exception as e:
        error_message = f"Error in process_quip_event: {e}"
        print(f"Pipeline failed and errors that most likely not being captured in BigQuery: {e}")
        
        raise

def handle_ecg_log(ecg_log_path, quip_id, vin):
    """Handles parsing and processing of the ECG log file."""
    # parsed_data = ecg_log_parser.parse_ecg_log(ecg_log_path)
    # if parsed_data:
    # ecg_log_parser.process_parsed_data(parsed_data)

    # Use detect_null_situation with quip_id and vin
    ecg_log_filename = os.path.basename(ecg_log_path)
    analysis = ecg_log_parser.detect_null_situation(ecg_log_filename, quip_id, vin)
    print(f"-----------------------------------------------------------------------------------------------")
    print(f"Null situation analysis: {analysis}")



def process_quip(args, processing_quip_id, quip_path):

    try:
        # Initializing logger with quip id
        logger_util.LogUtil.quip_id = processing_quip_id
        ResultData.start_time = datetime.now()

        print(f"Starting QUIP processing, creating jira.create_empty_result_dataframe")
        jira.create_empty_result_dataframe(processing_quip_id, ResultData.start_time.isoformat(), "Default - no conditions met")

        vndl_filename_gz = functions.get_vndl_file_name(quip_path)

        # Check for missing VNDL FIle and exit if not found
        if vndl_filename_gz is None:
            error_message = f'Missing Vndl file for: {processing_quip_id}'
            logger_util.error(error_message, FileNotFoundError,
                              Status.RUNQUIP_ERROR_VNDL_MMISSING, vndl_filename_gz)
            ResultData.quip_status.append(WakeEvents.VNDL_FILE_NOT_EXISTS)
            
            return

        extractgzfiles.extract_gz_files(quip_path, args.gcs_bucket_input_quip, args.gcs_bucket_prefix_quip)



        vndl_filename_dat = vndl_filename_gz[:-3]
        try:
            ascvndlconvertor.convert_dat_format(vndl_filename_dat)
        except Exception as e:
            error_message = "Conversion Failed"
            logger_util.error(error_message, e, Status.RUNQUIP_ERROR_VNDL_DAT_ASC_CONVERSION, vndl_filename_dat)
            ResultData.quip_status.append(WakeEvents.ASC_DAT_CONVERSION_DATA_ISSUE)
            

        logger_util.info(f"Done  dat -> asc conversion for {vndl_filename_dat} ", Status.RUNQUIP_PROCESSING,
                         vndl_filename_dat)
        ResultData.quip_status.append(WakeEvents.ASC_DAT_CONVERSION_NO_DATA_ISSUE)

        # ECG log processing
        ecg_log_filename = functions.get_ecg_file_path(processing_quip_id)

        
        health_check = False
        try:
            vndl_filename_asc = vndl_filename_dat[:-3] + "asc"

            [health_check, evnum_check, vndl_df] = vndl_health_check.vndl_health_check(vndl_filename_asc)
        except Exception as e:
            error_message = "Health check Failed"
            print(e)
            logger_util.error(error_message, e, Status.RUNQUIP_ERROR_HEALTH_CHECK_FAILED, "")
            

        ResultData.quip_status.append(WakeEvents.VNDL_HEALTH_CHECK_STATUS_ZERO)
        logger_util.info(f"Done health check for {processing_quip_id}: {health_check}", Status.RUNQUIP_HEALTH_CHECK, "")


    except Exception as e:
        error_message = f"Error in process_quip: {e}"
        logger_util.error(error_message, e, Status.PROCESS_QUIP_ERROR, processing_quip_id)
        

    skip_jira = False


        # jira
        
    ram_dump = None  # Initialize ram_dump to avoid undefined variable error
    if health_check and not skip_jira:
        try:
            jira_tag, vndl_dbc_joined_df = jira.jira(processing_quip_id, args.data_date, args.ram_dump, vndl_df,
                                                     evnum_check)
        except Exception as e:
            error_message = "Jira Failed"
            logger_util.error(error_message, e, Status.RUNQUIP_ERROR_JIRA_FAILED, "")
            

        ResultData.quip_status.append(WakeEvents.JIRA_LABEL_DATA_ISSUE)
        logger_util.info(f"Done jira check for {processing_quip_id}: {jira_tag}", Status.RUNQUIP_JIRA_CHECK, "")

        # gap analysis
        if jira_tag == 'jira':
            try:


                time_gap_analysis.total_gap(vndl_dbc_joined_df, constants.time_total_gap_variable, processing_quip_id,
                                            args.data_date)

                time_gap_analysis.partial_gap(vndl_dbc_joined_df, constants.time_parital_gap_variable_low,
                                              constants.time_parital_gap_variable_high, processing_quip_id,
                                              args.data_date)
            except Exception as e:
                error_message = "Timegap Analysis Failed"
                logger_util.error(error_message, e, Status.RUNQUIP_ERROR_TIMEGAP_FAILED, "")
                


            logger_util.info(f"Done gap analysis for {processing_quip_id}", Status.RUNQUIP_TIMEGAP_ANALYSIS, "")
            ResultData.quip_status.append(WakeEvents.GAP_ANALYSIS_DATA_ISSUE)

        # upload results directory to GCS
        # add gcs self retry on each file while uploading
        # functions.clean_path(Path(constants.QUIP_PATH))
        upload_from_directory(constants.RESULT_PATH + constants.job_tag + "/",
                              args.gcs_bucket_input_quip,
                              dest_blob_prefix=args.gcs_bucket_prefix_quip + constants.RESULT_PATH)

        # clean up
        # functions.clean_path(Path(constants.RESULT_PATH))
        logger_util.info(
            f"Result upload to gs://{args.gcs_bucket_input_quip + '/' + args.gcs_bucket_prefix_quip + constants.RESULT_PATH + constants.job_tag + '/'}",
            Status.RUNQUIP_RESULTS, constants.job_tag)
        logger_util.info("QUIP Processing Completed", Status.RAMDUMP_COMPLETED, "")
        try:
            ResultData.quip_status.append(WakeEvents.COMPLETED_PROCESSING)
        except Exception as e:
            error_message = f"Error in process_quip: Unexpected error - {e}"  # More general message
            logger_util.error(error_message, e, Status.PROCESS_QUIP_ERROR, processing_quip_id)
            

    else:
        print(f"Creating jira.create_empty_result_dataframe")
        jira.create_empty_result_dataframe(processing_quip_id, ResultData.start_time.isoformat(), "VNDL Health Check is False")


  
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    max_retries = 1  # Number of retries
    retry_delay = 5  # Delay in seconds between retries (adjust as needed)

    for attempt in range(max_retries + 1):  # Retry loop
        try:
            process_quip_event(parser)
            print("process_quip_event completed successfully.")  # Optional: Success message
            break  # Exit the loop if successful
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")  # Print attempt number

            error_message = f"Error in process_quip (Attempt {attempt + 1}): {e}"  #Include attempt number
            logger_util.error(error_message, e, Status.PROCESS_QUIP_ERROR, '')
            

            if attempt < max_retries:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)  # Wait before retrying
            else:
                print("Max retries reached.  Process failed.") # Final failure message
