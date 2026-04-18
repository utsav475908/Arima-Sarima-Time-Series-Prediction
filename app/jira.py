import os

import numpy as np
import pandas as pd

import column_names
import constants
import dbc_parsing
import ecg_fnv_logic
import ecg_log_parser
import filter_dbc_wakeup_signals
import functions
import logger_util
import process_results as results
import ramdump_parsing
import software_version
import vin_identification
import vndl_dbc_joining
import write_report
from status import Status


def create_empty_result_dataframe(quip_id, data_date, no_jira_comment):
    vin = vin_identification.vin_identification()

    no_jira_result = functions.create_empty_df(column_names.QUIP)
    no_jira_result.loc[0, column_names.QUIP] = quip_id
    no_jira_result.loc[0, column_names.COMMENT] = no_jira_comment
    no_jira_result.loc[0, column_names.LABEL] = 'no_jira'
    no_jira_result.loc[0, column_names.VIN] = vin
    no_jira_result.loc[0, column_names.RUNNING_DATE] = constants.running_datetime
    no_jira_result.loc[0, column_names.DATA_DATE] = data_date
    no_jira_result.loc[0, column_names.ECG_EVENT] = None

    # Set other required columns to None or appropriate default values
    column_list = [column_names.EXPLAINABLE_BUS_NAME, column_names.EXPLAINABLE_BUS_ID,
                   column_names.EXPLAINABLE_MESSAGE_DESC, column_names.EXPLAINABLE_MESSAGE_ID,
                   column_names.EXPLAINABLE_SIGNAL_DESC, column_names.EXPLAINABLE_SIGNAL_MEANING,
                   column_names.EXPLAINABLE_SIGNAL_VALUE, column_names.NUMBER_LOCK_EVENTS,
                   column_names.VNDL, column_names.VNDL_DECODE_DBC, column_names.PROGRAM,
                   column_names.VNDL_STRT_DATE]
    no_jira_result[column_list] = None
    results.ResultData.wake_signals = no_jira_result


def jira(quip_id, data_date, ram_dump, vndl_df, evnum_check):
    logger_util.info(f"JIRA Process Started for data date {data_date}", Status.JIRA_STARTED, "")

    vin = vin_identification.vin_identification()
    ecg_event_value = None
    # try:
    ecg_event = ecg_fnv_logic.parse_ecg_event(quip_id)
    logger_util.info(f'ecg event is: {ecg_event}', Status.JIRA_PROCESSING, constants.ECG_FILE_NAME)
    if len(ecg_event) > 0:
        ecg_event_value = ecg_event[column_names.ECG_EVENT].values[0]
    # except:
    #     logger_util.info("ecg event issue", Status.JIRA_PROCESSING, constants.ECG_FILE_NAME)
    #     ecg_event = functions.create_empty_df(column_names.QUIP)
    #     column_list = [column_names.ECG_EVENT]
    #     ecg_event[column_list] = None

    # before ramdump parsing, check ramdump for reflash signal.  If it is a reflash, then exit code.
    # parse the ramdump file based on the given QUIP ID
    reflash_flag = False
    try:
        reflash_final, reflash_dg_final = ramdump_parsing.user_reflash_filter(quip_id, ram_dump)

        reflash_final = pd.concat([reflash_final, reflash_dg_final], ignore_index=True)
        
        if len(reflash_final) > 0:
            reflash_final[column_names.COMMENT] = 'Reflash signal found, event is caused by Tester/VDR'
            reflash_final[column_names.LABEL] = 'no_jira'
            vndl_jira_tag = 'no_jira'
            vndl_dbc_joined_df=functions.create_empty_df("empty")
            reflash_final[column_names.VIN] = vin
            reflash_final[column_names.RUNNING_DATE] = constants.running_datetime
            reflash_final[column_names.DATA_DATE] = data_date
            logger_util.info(f'flash_signal {reflash_final}', Status.JIRA_PROCESSING, constants.RAMDUMP_FILE_NAME)

            os.chdir(results.ProcessPaths.root_directory)

            reflash_final = pd.merge(reflash_final, ecg_event, on=column_names.QUIP, how='inner')
            reflash_final = pd.DataFrame(reflash_final,
                                         columns=[column_names.QUIP,
                                                  column_names.COMMENT,
                                                  column_names.EXPLAINABLE_BUS_NAME,
                                                  column_names.EXPLAINABLE_BUS_ID,
                                                  column_names.EXPLAINABLE_MESSAGE_DESC,
                                                  column_names.EXPLAINABLE_MESSAGE_ID,
                                                  column_names.EXPLAINABLE_SIGNAL_DESC,
                                                  column_names.EXPLAINABLE_SIGNAL_MEANING,
                                                  column_names.EXPLAINABLE_SIGNAL_VALUE,
                                                  column_names.LABEL,
                                                  column_names.NUMBER_LOCK_EVENTS,
                                                  column_names.VIN,
                                                  # column_names.NUM_OF_BUS_ID,
                                                  column_names.VNDL,
                                                  column_names.VNDL_DECODE_DBC,
                                                  column_names.PROGRAM,
                                                  column_names.VNDL_STRT_DATE,
                                                  column_names.RUNNING_DATE,
                                                  column_names.ECG_EVENT,
                                                  column_names.DATA_DATE])

            # Saving data into results
            results.ResultData.wake_signals = reflash_final
            reflash_final.to_csv(constants.RESULT_PATH + constants.job_tag + '/' + quip_id + '_wake_signal.csv',
                                 index=False, date_format='%Y-%m-%d %H:%M:%S')
            reflash_flag = True
    except Exception as e:
        logger_util.error("Problem in reflash signal : ", e, Status.JIRA_PROCESSING, constants.RAMDUMP_FILE_NAME)

    # parse the ramdump file based on the given QUIP ID
    if not reflash_flag:
        ramdump_df, ramdump_df_grp_channel_module_msg = parse_ramdump(ram_dump)
        print(f"in  reflash block in Jira ramdump_df: {ramdump_df}")
        # if the ramdump_df is empty, or all the values for module column are None, then enter the the blocl



        if ramdump_df.empty or ramdump_df['module'].isnull().all():
        # if  ramdump_df['module'].iloc[0] is None:

            logger_util.info("No valid modules found in ramdump, calling detect_null_situation_ramdump", Status.RAMDUMP_PROCESSING, ram_dump)
            
            # Call detect_null_situation_amdump to get module list
            null_modules = ecg_log_parser.detect_null_situation_ramdump(None)
            
            # Check if any module is 'tester present' or 'OTA'
            no_jira_flag = False
            no_jira_comment = None
            
            if null_modules:
                for module in null_modules:
                    module_str = str(module).lower()
                    if 'external tester' in module_str or 'ota' in module_str:
                        no_jira_flag = True
                        no_jira_comment = f"Found: {module}"
                        break
                        # break
                
                # Create new rows for each module returned by detect_null_situation_ramdump
                new_rows = []
                for module in null_modules:
                    new_row = {
                        column_names.RAMDUMP_TIMESTAMP: None,
                        column_names.RAMDUMP_CHANNEL: None,
                        column_names.RAMDUMP_MODULE: str(module),
                        column_names.RAMDUMP_FIRST_MSG_AFTER_BUS_WAKE: None,
                        column_names.VNDL: ramdump_df.get(column_names.VNDL).iloc[0] if not ramdump_df.empty and column_names.VNDL in ramdump_df else None,
                        'wmcheckcpwakeup_flag': ramdump_df.get('wmcheckcpwakeup_flag').iloc[0] if not ramdump_df.empty and 'wmcheckcpwakeup_flag' in ramdump_df else None,
                    }
                    new_rows.append(new_row)
                
                # Create DataFrame from new rows
                df = pd.DataFrame(new_rows)

                # make ramdump df equal to df
                ramdump_df = df

                logger_util.info(f"Created {len(new_rows)} rows from detect_null_situation_ramdump results", Status.RAMDUMP_PROCESSING, ram_dump)
                
                # If no_jira condition is met, create the no_jira result and return early
                if no_jira_flag:
                    no_jira_result = functions.create_empty_df(column_names.QUIP)
                    no_jira_result.loc[0, column_names.QUIP] = quip_id
                    no_jira_result.loc[0, column_names.COMMENT] = no_jira_comment
                    no_jira_result.loc[0, column_names.LABEL] = 'no_jira'
                    no_jira_result.loc[0, column_names.VIN] = vin
                    no_jira_result.loc[0, column_names.RUNNING_DATE] = constants.running_datetime
                    no_jira_result.loc[0, column_names.DATA_DATE] = data_date
                    no_jira_result.loc[0, column_names.ECG_EVENT] = ecg_event_value
                    
                    # Set other required columns to None or appropriate default values
                    column_list = [column_names.EXPLAINABLE_BUS_NAME, column_names.EXPLAINABLE_BUS_ID,
                                  column_names.EXPLAINABLE_MESSAGE_DESC, column_names.EXPLAINABLE_MESSAGE_ID,
                                  column_names.EXPLAINABLE_SIGNAL_DESC, column_names.EXPLAINABLE_SIGNAL_MEANING,
                                  column_names.EXPLAINABLE_SIGNAL_VALUE, column_names.NUMBER_LOCK_EVENTS,
                                  column_names.VNDL, column_names.VNDL_DECODE_DBC, column_names.PROGRAM,
                                  column_names.VNDL_STRT_DATE]
                    no_jira_result[column_list] = None
                    
                    # Save the result
                    results.ResultData.wake_signals = no_jira_result
                    # no_jira_result.to_csv(constants.RESULT_PATH + constants.job_tag + '/' + quip_id + '_wake_signal.csv',
                    #                      index=False, date_format='%Y-%m-%d %H:%M:%S')
                    
                    logger_util.info(f"No JIRA created due to {no_jira_comment}", Status.JIRA_PROCESSING, ram_dump)
                    return 'no_jira', None
        





        # parse the associated dbc file
        os.chdir(results.ProcessPaths.root_directory)

        program_from_vndl = vndl_df.iloc[0][column_names.DBC_FILE]
        [dbc_df, working_dbc_file] = dbc_parsing.dbc_parsing_gcs(program_from_vndl + '.xlsx')

        # join the parsed vndl and dbc files
        vndl_dbc_joined_df = vndl_dbc_joining.vndl_dbc_joining(vndl_df, dbc_df)

        # get the software version info
        try:
            ecg_os_df = software_version.software_version(quip_id)
            if vin:
                ecg_os_df[column_names.VIN] = vin
            else:
                ecg_os_df = functions.create_empty_df(column_names.VIN)
                ecg_os_df.loc[0, column_names.VIN] = None
                column_list = [column_names.SOFTWARE_VERSION,
                               column_names.OS_VERSION,
                               column_names.BUILD_VARIANT,
                               column_names.DEVICE_TYPE,
                               column_names.OS_BUILD_DATE,
                               column_names.ECG_API_VERSION,
                               column_names.ECG_IPC_VERSION]
                ecg_os_df[column_list] = None
        except Exception as e:
            logger_util.error("ecg os info parsing issue", e, Status.JIRA_PROCESSING, constants.ECG_OS_INFO_FILE_NAME)
            ecg_os_df = functions.create_empty_df(column_names.VIN)
            ecg_os_df.loc[0, column_names.VIN] = vin
            column_list = [column_names.SOFTWARE_VERSION,
                           column_names.OS_VERSION,
                           column_names.BUILD_VARIANT,
                           column_names.DEVICE_TYPE,
                           column_names.OS_BUILD_DATE,
                           column_names.ECG_API_VERSION,
                           column_names.ECG_IPC_VERSION]
            ecg_os_df[column_list] = None

        vndl_dbc_factory_mode_check = filter_dbc_wakeup_signals.factory_mode_check(quip_id, vndl_dbc_joined_df,
                                                                                   ecg_os_df, working_dbc_file,
                                                                                   data_date, program_from_vndl)
        print('factory mode df')
        print(vndl_dbc_factory_mode_check)
        # if vndl_dbc_agg[column_names.LABEL][0] == "no_jira":
        if not vndl_dbc_factory_mode_check.empty:
            vndl_dbc_factory_mode_check = pd.DataFrame(vndl_dbc_factory_mode_check,
                                                       columns=[column_names.QUIP,
                                                                column_names.COMMENT,
                                                                column_names.EXPLAINABLE_BUS_NAME,
                                                                column_names.EXPLAINABLE_BUS_ID,
                                                                column_names.EXPLAINABLE_MESSAGE_DESC,
                                                                column_names.EXPLAINABLE_MESSAGE_ID,
                                                                column_names.EXPLAINABLE_SIGNAL_DESC,
                                                                column_names.EXPLAINABLE_SIGNAL_MEANING,
                                                                column_names.EXPLAINABLE_SIGNAL_VALUE,
                                                                column_names.LABEL,
                                                                column_names.NUMBER_LOCK_EVENTS,
                                                                column_names.VIN,
                                                                # column_names.NUM_OF_BUS_ID,
                                                                column_names.VNDL,
                                                                column_names.VNDL_DECODE_DBC,
                                                                column_names.PROGRAM,
                                                                column_names.VNDL_STRT_DATE,
                                                                column_names.RUNNING_DATE,
                                                                column_names.ECG_EVENT,
                                                                column_names.DATA_DATE
                                                                ])
            vndl_dbc_factory_mode_check[column_names.ECG_EVENT] = ecg_event_value
            logger_util.info(vndl_dbc_factory_mode_check.to_string(), Status.JIRA_PROCESSING, "vndl_file")

            # Saving data into results
            results.ResultData.wake_signals = vndl_dbc_factory_mode_check
            vndl_dbc_factory_mode_check.to_csv(constants.RESULT_PATH + constants.job_tag + '/' + quip_id +
                                               '_wake_signal.csv', index=False, date_format='%Y-%m-%d %H:%M:%S')

            return 'None', None
        else:

            wake_signal_df = filter_dbc_wakeup_signals.filter_dbc_wakeup_signals(vndl_dbc_joined_df, ecg_os_df,
                                                                                 working_dbc_file, quip_id, evnum_check)

            wake_signal_df = pd.merge(wake_signal_df, ecg_event, on=column_names.QUIP, how='outer')
            print(f"This is for debugging purposes only, Jira.py line 255:\n {wake_signal_df.head()}")

            vndl_jira = wake_signal_df[[column_names.QUIP, column_names.VIN, column_names.LABEL]].drop_duplicates()

            write_report.write_report(ramdump_df, ramdump_df_grp_channel_module_msg, working_dbc_file,
                                      wake_signal_df, program_from_vndl, quip_id, data_date)


            vndl_jira_tag = vndl_jira[column_names.LABEL][0]
            logger_util.info(f'jira tag is: {vndl_jira_tag}', Status.JIRA_PROCESSING, "")

    logger_util.info("JIRA Process Completed", Status.JIRA_COMPLETED, "")

    return vndl_jira_tag, vndl_dbc_joined_df


def parse_ramdump(ram_dump):
    try:
        ramdump_df = ramdump_parsing.ram_dump_parsing(ram_dump)
        if len(ramdump_df) == 0:
            #raise Exception('empty ramdump')
            logger_util.info("Empty ramdump", Status.JIRA_PROCESSING, constants.RAMDUMP_FILE_NAME)
            ramdump_df.loc[0, column_names.VNDL] = functions.get_vndl_asc_file_name()
    except Exception as e:
        # create an empty dataframe: cases: in case of missing ramdump file or any  error in parsing ramdumpfile
        #logger_util.error("Ramdump parsing issue", e, Status.JIRA_PROCESSING, constants.RAMDUMP_FILE_NAME)
        logger_util.info("Ramdump parsing issue", Status.JIRA_PROCESSING, constants.RAMDUMP_FILE_NAME)
        ramdump_df = functions.create_empty_df(column_names.VNDL)
        ramdump_df.loc[0, column_names.VNDL] = functions.get_vndl_asc_file_name()
        column_list = [column_names.RAMDUMP_TIMESTAMP, column_names.RAMDUMP_CHANNEL, column_names.RAMDUMP_MODULE,
                       column_names.RAMDUMP_FIRST_MSG_AFTER_BUS_WAKE,
                       column_names.WMCHECKCPWAKEUP_FLAG]
        ramdump_df[column_list] = None

    # summarized results coming from ramdump df
    ramdump_df_grp_channel = ramdump_df.groupby([column_names.RAMDUMP_CHANNEL], dropna=False) \
        .size().reset_index(name=column_names.WAKE_COUNTS)

    # Calculating Percentage
    ramdump_df_grp_channel[column_names.WAKE_PERCENT] = (ramdump_df_grp_channel[column_names.WAKE_COUNTS]
                                                         / ramdump_df_grp_channel[
                                                             column_names.WAKE_COUNTS].sum()) * 100

    ramdump_df_grp_channel_module = ramdump_df.groupby([column_names.RAMDUMP_CHANNEL, column_names.RAMDUMP_MODULE],
                                                       dropna=False).size().reset_index(
        name=column_names.WAKE_COUNTS)

    # Calculating Percentage
    ramdump_df_grp_channel_module[column_names.WAKE_PERCENT] = \
        (ramdump_df_grp_channel_module[column_names.WAKE_COUNTS] /
         ramdump_df_grp_channel_module[column_names.WAKE_COUNTS].sum()) * 100

    ramdump_df_grp_channel_module_msg = ramdump_df \
        .groupby([column_names.RAMDUMP_CHANNEL, column_names.RAMDUMP_MODULE,
                  column_names.RAMDUMP_FIRST_MSG_AFTER_BUS_WAKE, column_names.WMCHECKCPWAKEUP_FLAG], dropna=False) \
        .size().reset_index(name=column_names.WAKE_COUNTS)

    # Calculating Percentage
    ramdump_df_grp_channel_module_msg[column_names.WAKE_PERCENT] = \
        (ramdump_df_grp_channel_module_msg[column_names.WAKE_COUNTS] /
         ramdump_df_grp_channel_module_msg[column_names.WAKE_COUNTS].sum()) * 100

    logger_util.info(f"ramdump_df_grp_channel_module_msg dataframe is {ramdump_df_grp_channel_module_msg}", Status.JIRA_PROCESSING, constants.RAMDUMP_FILE_NAME)
    return ramdump_df, ramdump_df_grp_channel_module_msg
