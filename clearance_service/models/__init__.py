import os

import acslib

acs_system = os.getenv("ACS_SYSTEM").lower()
if acs_system != "ccure":
    raise OSError("The ACS_SYSTEM variable must be set to 'ccure'.")

acs = acslib.CcureAPI()
filters = acslib.ccure.filters
