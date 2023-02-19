from enum import Enum
from collections import namedtuple

class Hydrophone(Enum):
    """
    Enum for orcasound hydrophones, including AWS S3 Bucket info
    """

    HPhoneTup = namedtuple("Hydrophone", "bucket ref_folder")

    BUSH_POINT = HPhoneTup("streaming-orcasound-net", "rpi_bush_point")
    ORCASOUND_LAB = HPhoneTup("streaming-orcasound-net", "rpi_orcasound_lab")
    PORT_TOWNSEND = HPhoneTup("streaming-orcasound-net", "rpi_port_townsend")
    SUNSET_BAY = HPhoneTup("streaming-orcasound-net", "rpi_sunset_bay")
    SANDBOX = HPhoneTup("acoustic-sandbox", "orcasounds")