from enum import Enum
from collections import namedtuple

class Hydrophone(Enum):
    """
    Enum for orcasound hydrophones, including AWS S3 Bucket info
    """

    HPhoneTup = namedtuple("Hydrophone", "name bucket ref_folder save_bucket save_folder")

    BUSH_POINT = HPhoneTup("bush_point", "streaming-orcasound-net", "rpi_bush_point", "acoustic-sandbox", "bush_point")
    ORCASOUND_LAB = HPhoneTup("orcasound_lab", "streaming-orcasound-net", "rpi_orcasound_lab", "acoustic-sandbox", "orcasound_lab")
    PORT_TOWNSEND = HPhoneTup("port_townsend", "streaming-orcasound-net", "rpi_port_townsend", "acoustic-sandbox", "port_townsend")
    SUNSET_BAY = HPhoneTup("sunset_bay", "streaming-orcasound-net", "rpi_sunset_bay", "acoustic-sandbox", "sunset_bay")
    SANDBOX = HPhoneTup("sandbox", "acoustic-sandbox", "orcasounds", "acoustic-sandbox", "orcasounds")