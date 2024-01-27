import utilities as util
import datetime as dt
from enum import Enum
from collections import namedtuple
import soundfile as sf
import numpy as np
import matplotlib.pyplot as plt
import csv
'''
    Extract ts segments for selected time interval and save as wav files
    Code was extracted from https://github.com/orcasound/ambient-sound-analysis
    The procedure gdownloadWavs was extracted from the students' pipeline
        Note that pipeline.py, hydrophone.py, file_connector.py and acoustic_util.py are stored in this folder
    Thanks go to U W Masters students:  
        Caleb Case
        Mitch Haldeman
        Grant Savage
    Make sure that the needed dependencies are installed  pip install -r requirements.txt    
    Specify directory for the wav files and start/stop datetimes
'''



class Hydrophone(Enum):
    """
    Enum for orcasound hydrophones, including AWS S3 Bucket info
    """

    HPhoneTup = namedtuple("Hydrophone", "name bucket ref_folder save_bucket save_folder")

    BUSH_POINT = HPhoneTup("bush_point", "streaming-orcasound-net", "rpi_bush_point", "acoustic-sandbox", "ambient-sound-analysis/bush_point")
    ORCASOUND_LAB = HPhoneTup("orcasound_lab", "streaming-orcasound-net", "rpi_orcasound_lab", "acoustic-sandbox", "ambient-sound-analysis/orcasound_lab")
    PORT_TOWNSEND = HPhoneTup("port_townsend", "streaming-orcasound-net", "rpi_port_townsend", "acoustic-sandbox", "ambient-sound-analysis/port_townsend")
    SUNSET_BAY = HPhoneTup("sunset_bay", "streaming-orcasound-net", "rpi_sunset_bay", "acoustic-sandbox", "ambient-sound-analysis/sunset_bay")
    SANDBOX = HPhoneTup("sandbox", "acoustic-sandbox", "ambient-sound-analysis", "acoustic-sandbox", "ambient-sound-analysis")




wavDir = "/home/val/Music/WAVfiles4Comparison/"
dt_start = dt.datetime(2023, 3, 22, 11, 0)
dt_stop =  dt.datetime(2023, 3, 22, 11, 10)
hydro =  Hydrophone['PORT_TOWNSEND']
startSecs =5*60 + 25  # 5 min and 25 seconds
deltaT = 60  # one minute psd's

calConstant = 0 #-35
Nfft = 2048
# Choose "Hamming" or "Blackman"
fftWindow = "Blackman"
fftWindow = "Hamming"

wavFileList = []   # switch with wav file line to process wav file already download from ts segments
wavFileList = [wavDir + 'rpi-port-townsend_2023_03_22_11_00_00.wav']

outputCSVfile = wavDir + 'psdCSVfile.csv'
wavFileSecs = 9e9 #15 * 60  # set maximum number of seconds in single wav file

t1 = dt.datetime.now()
if len(wavFileList) == 0: wavFileList = util.get_wav_files(wavDir,hydro, dt_start, dt_stop, wavFileLength_seconds = min((dt_stop - dt_start).total_seconds(), wavFileSecs))
t2 = dt.datetime.now()
print(f"Elapsed time for this download and conversion is {(t2 - t1).total_seconds()/60:.2f} minutes")
print("Wav File List: ", wavFileList)
with sf.SoundFile(wavFileList[0]) as f:
    samplerate = f.samplerate
fhigh = samplerate/2  # set high frequency cutoff at the Nyquist frequency
Nsamples = int(deltaT*samplerate)

showPlotInterpolation = True
freqPerHz, psdPerHz = util.calculatePSD(wavFileList[0], samplerate, startSecs, Nsamples, fhigh, Nfft, fftWindow, calConstant, showPlotInterpolation)


fig, ax = plt.subplots(figsize=(12, 6))
thefile = wavFileList[0].split('/')[-1]
title = "{:0.2f} s in {}".format(startSecs, thefile)
fig.suptitle(title)
ax.plot(freqPerHz, psdPerHz, color = 'red', linewidth = 1)
plt.show()

with open(outputCSVfile, "w", newline="") as csvfile:  # Ensure consistent line endings
    writer = csv.writer(csvfile)
    # Write the array to the CSV file
    writer.writerows(psdPerHz.reshape(-1, 1))
