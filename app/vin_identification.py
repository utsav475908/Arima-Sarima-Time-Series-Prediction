import json
from json import JSONDecodeError

import constants
import logger_util
import column_names
from process_results import ResultData
from status import Status, WakeEvents


def vin_identification():
    logger_util.info("Starting...", Status.VINIDENTIFICATION_STARTED, constants.CLIENT_OFFER_FILE_NAME)

    try:
        json_file = open(constants.CLIENT_OFFER_FILE_NAME)
        ResultData.quip_status.append(WakeEvents.CLIENT_OFFER_JSON_EXISTS)
        # return json object as a dictionary
        json_data = json.load(json_file)
        vin = json_data['childEvent']['vehicleDimension'][column_names.VIN]
        json_file.close()
        ResultData.quip_status.append(WakeEvents.CLIENT_OFFER_JSON_NO_DATA_ISSUE)
        return vin
    except FileNotFoundError as fne:
        logger_util.info(f'Missing File {constants.CLIENT_OFFER_FILE_NAME}',
                          Status.VINIDENTIFICATION_ERROR_CLIENT_OFFER_NOT_FOUND, constants.CLIENT_OFFER_FILE_NAME)

        ResultData.quip_status.append(WakeEvents.CLIENT_OFFER_JSON_NOT_EXISTS)

    except JSONDecodeError as jde:
        logger_util.error('JSONDecodeError while reading client-offer.json', jde,
                          Status.VINIDENTIFICATION_ERROR_JSON_DECODE_FAILED, constants.CLIENT_OFFER_FILE_NAME)

        ResultData.quip_status.append(WakeEvents.CLIENT_OFFER_JSON_DATA_ISSUE)

    except TypeError as te:
        logger_util.error('TypeError while reading client-offer.json', te,
                          Status.VINIDENTIFICATION_ERROR_TYPE_ERROR, constants.CLIENT_OFFER_FILE_NAME)

        ResultData.quip_status.append(WakeEvents.CLIENT_OFFER_JSON_DATA_ISSUE)

    logger_util.info("Completed...", Status.VINIDENTIFICATION_COMPLETED, constants.CLIENT_OFFER_FILE_NAME)
    return None
