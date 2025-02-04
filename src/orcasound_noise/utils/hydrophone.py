from enum import Enum
from collections import namedtuple

class Hydrophone(Enum):
    """
    Enum for orcasound hydrophones, including AWS S3 Bucket info
    """

    HPhoneTup = namedtuple("Hydrophone", "name bucket ref_folder save_bucket save_folder bb_ref")

    BUSH_POINT = HPhoneTup("bush_point", "audio-orcasound-net", "rpi_bush_point", "acoustic-sandbox", "ambient-sound-analysis/bush_point", 71.6406580028601)
    ORCASOUND_LAB = HPhoneTup("orcasound_lab", "audio-orcasound-net", "rpi_orcasound_lab", "acoustic-sandbox", "ambient-sound-analysis/orcasound_lab", 71.6406580028601)
    PORT_TOWNSEND = HPhoneTup("port_townsend", "audio-orcasound-net", "rpi_port_townsend", "acoustic-sandbox", "ambient-sound-analysis/port_townsend", 71.6406580028601)
    SUNSET_BAY = HPhoneTup("sunset_bay", "audio-orcasound-net", "rpi_sunset_bay", "acoustic-sandbox", "ambient-sound-analysis/sunset_bay", 71.6406580028601)
    SANDBOX = HPhoneTup("sandbox", "acoustic-sandbox", "ambient-sound-analysis", "acoustic-sandbox", "ambient-sound-analysis", 71.6406580028601)
