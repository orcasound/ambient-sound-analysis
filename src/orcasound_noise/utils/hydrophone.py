from enum import Enum
from collections import namedtuple

class Hydrophone(Enum):
    """
    Enum for orcasound hydrophones, including AWS S3 Bucket info
    """

    HPhoneTup = namedtuple("Hydrophone", "name bucket ref_folder save_bucket save_folder bookmark_folder bb_ref")

    BUSH_POINT = HPhoneTup("bush_point", "audio-orcasound-net", "rpi_bush_point", "acoustic-sandbox", "ambient-sound-analysis/data_3.0", "ambient-sound-analysis", 71.6406580028601)
    ORCASOUND_LAB = HPhoneTup("orcasound_lab", "audio-orcasound-net", "rpi_orcasound_lab", "acoustic-sandbox", "ambient-sound-analysis/data_3.0", "ambient-sound-analysis", 71.6406580028601)
    PORT_TOWNSEND = HPhoneTup("port_townsend", "audio-orcasound-net", "rpi_port_townsend", "acoustic-sandbox", "ambient-sound-analysis/data_3.0", "ambient-sound-analysis", 71.6406580028601)
    SUNSET_BAY = HPhoneTup("sunset_bay", "audio-orcasound-net", "rpi_sunset_bay", "acoustic-sandbox", "ambient-sound-analysis/data_3.0", "ambient-sound-analysis", 71.6406580028601)
    ANDREWS_BAY = HPhoneTup("andrews_bay", "audio-orcasound-net", "rpi_andrews_bay", "acoustic-sandbox", "ambient-sound-analysis/data_3.0", "ambient-sound-analysis", 71.6406580028601)
    MAST_CENTER = HPhoneTup("mast_center", "audio-orcasound-net", "rpi_mast_center", "acoustic-sandbox", "ambient-sound-analysis/data_3.0", "ambient-sound-analysis", 71.6406580028601)
    POINT_ROBINSON = HPhoneTup("point_robinson", "audio-orcasound-net", "rpi_point_robinson", "acoustic-sandbox", "ambient-sound-analysis/data_3.0", "ambient-sound-analysis", 71.6406580028601)
    NORTH_SJC = HPhoneTup("north_sjc", "audio-orcasound-net", "rpi_north_sjc", "acoustic-sandbox", "ambient-sound-analysis/data_3.0", "ambient-sound-analysis", 71.6406580028601)
    SANDBOX = HPhoneTup("sandbox", "acoustic-sandbox", "ambient-sound-analysis", "acoustic-sandbox", "ambient-sound-analysis/data_3.0", "ambient-sound-analysis", 71.6406580028601)
