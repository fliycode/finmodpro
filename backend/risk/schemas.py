RISK_EXTRACTION_JSON_SCHEMA = {
    "type": "json_object",
}


RISK_VERIFICATION_JSON_SCHEMA = {
    "type": "json_object",
}


def get_extraction_response_format():
    return RISK_EXTRACTION_JSON_SCHEMA


def get_verification_response_format():
    return RISK_VERIFICATION_JSON_SCHEMA
