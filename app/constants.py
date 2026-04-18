import getpass
import os
from glob import glob
import datetime

cdsid = getpass.getuser()
cwd = glob(os.getcwd() + "/*/", recursive=True)

# File names
GZ_EXTENSION = ".gz"
RAMDUMP_FILE_NAME = 'ecg_pwr_vmcu_ramdump.txt'
ECG_FILE_NAME = 'ecg_fnv_log.txt'
ECG_OS_INFO_FILE_NAME = 'ecg_os_info.txt'
CLIENT_OFFER_FILE_NAME = 'client-offer.json'
GZ_VNDL_DAT_FILE_NAME = '*_0.dat.gz'
VNDL_DAT_FILE_NAME = '*_0.dat'
VNDL_ASC_FILE_NAME = '*_0.asc'
XLSX = '.xlsx'
PKL = 'pkl'

# time_gap_variable is where the signal gap length is defined.  This is needed if a jira is issued, and
# the Time_gap.py module is run.  Default is 0.1 second
# time_gap_variable = 0.1
running_datetime = datetime.datetime.now().strftime("%Y-%m-%d")
job_tag = str(running_datetime)
DEFAULT_DBC_FILE_XLSX_VERSION = "Y2021_FNV2_CMDB_v21.08_Export.xlsx"
DEFAULT_DBC_FILE_DBC_VERSION = "Y2021_FNV2_CMDB_v21.08_"
DEFAULT_DBC_FILE_DBC_MS2_VERSION = "Y2021_FNV2_CMDB_v21.08_MS2.dbc"

time_gap_variable = 0.3
time_total_gap_variable = 0.3
time_parital_gap_variable_low = 1.0
time_parital_gap_variable_high = 2.0
time_parital_gap_buffer = 0.01


# BIN_2_DEC_LENGTH is a variable used in the dbc decoding process.  Default is 2
BIN_2_DEC_LENGTH = 2
REMOVE_BEGINNING_VNDL_TIME_SECS = 2

QUIP_PATH = 'QUIP_files/'
RESULT_PATH = 'results/'
PROCESSED_DATA_PATH = 'processed_data/'
LOGWORTHY_SYSTEM_PATH = 'logworthy/system/'
LOGWORTHY = 'logworthy'
ECG = 'ECG'
ECG_EVENT_VALUE = 'ecg_event_issue'
DBC_MAIN_PATH = 'dbc/'
DBC_XL_PATH = f"{DBC_MAIN_PATH}{XLSX}/"
DBC_XL_PATH_GCP = f"{DBC_MAIN_PATH}xlsx/"
DBC_PKL_PATH = f"{DBC_MAIN_PATH}{PKL}/"

# within input
RAMDUMP_FILE_NAME = "ecg_pwr_vmcu_ramdump.txt"

# JIRA LABELS
FOUND_EX_WAKE_SIGNALS = 'found explainable wake signal(s)'
JIRA_LABEL = 'jira'
NO_JIRA_LABEL = 'no_jira'


CHANNEL_ID_NAME_MAP = {
    '32': 'DG1',
    '64': 'FD1',
    '128': 'HS1',
    '256': 'HS2',
    '512': 'HS3',
    '1024': 'HS4',
    '2048': 'MS1',
    '4096': 'MS2'
}

VNDL_CHANNEL_ID_NAME_MAP = {
    'HS1': '1',
    'HS2': '2',
    'HS3': '3',
    'HS4': '4',
    'HS5': '5',
    'FD1': '6',
    'FD2': '7',
    'FD3': '8',
    'MS1': '9',
    'MS2': '10'
}

REVERSE_VNDL_CHANNEL_ID_NAME_MAP = {
    '1': 'HS1',
    '2': 'HS2',
    '3': 'HS3',
    '4': 'HS4',
    '5': 'HS5',
    '6': 'FD1',
    '7': 'FD2',
    '8': 'FD3',
    '9': 'MS1',
    '10': 'MS2'
}

# This is dynamic explainable list -- note if you add signals to this list, please keep values in decimal format
EXPLAINABLE_SIGNAL_WITH_PREDETERMINED_VALUE = {
    'VehWlcmFrwl_D_Stat': 1.0,
    'VehWlcmFrwlMde_D_Stat': [1.0, 2.0],
    'DrStatDrv_B_Act': 1.0,
    'DrStatPsngr_B_Actl': 1.0,
    'DrStatTgate_B_Actl': 1.0,
    'DrStatRr_B_Actl': 1.0,
    'DrStatRl_B_Actl': 1.0,
    'DrStatHood_B_Actl': 1.0,
    'Key_In_Ignition_Stat': 1.0,
    'Power_Up_Chime_Modules': 1.0
}

# This is a list of primary signals -- if we find one of these signals as the only explainable signal,
# we will then check for number of state changes.  If num state changes is <10, then mark as "no_jira"
PRIMARY_SIGNALS = {
    'Ignition_Status',
    'HeadLghtSwtch_D_Stat',
    'HazrdLght_B_Stat',
    'Eng_D_Stat',
    'Courtesy_Bsave_Stat',
    'Delay_Accy',
    'Remote_Start_Status',
    'Remote_Start_Req',
    'Parklamp_Status'
}

# This is a list of secondary signals -- if we find up to two of these signals and they are the only
# explainable signals,
# we will then check for number of state changes.  If num state changes is 0 or >10 then mark as "jira"
SECONDARY_SIGNALS = {
    'DrStatDrv_B_Actl',
    'DrStatPsngr_B_Actl',
    'DrStatTgate_B_Actl',
    'DrStatRr_B_Actl',
    'DrStatRl_B_Actl',
    'DrStatHood_B_Actl',
    'Power_Up_Chime_Modules',
    'VehWlcmFrwlMde_D_Stat',
    'Veh_Lock_Requestor',
    'TurnLghtLeftOn_B_Stat',
    'TurnLghtRightOn_B_Stat',
    'HeadLghtHiOn_B_Stat',
    'HeadLampLoActv_B_Stat',
    'HMI_HMIMode_St',
    'PlgActvArb_B_Actl',
    'PlgActvArb_B_Dsply',
    'ChrgrInPwMde_D_Actl',
    'ChrgrCnnctPwr_B_Stat',
    'ChrgrRdyStat_D_Actl',
    'ULoBattTrnsfrSustn_B_Rq',
    'ULoBattSpprtSustn_B_Rq',
    'BattTracCnnct_D_Cmd',
    'Courtesy_Delay_Status',
    'VehWlcmFrwl_D_Stat',
    'Key_In_Ignition_Stat',
    'Shed_Level_Req',
    'Veh_Lock_EvNum',
    'Veh_Lock_Status',
    'PudLamp_D_Rq',
    'PrkLght_D_Stat'
}
