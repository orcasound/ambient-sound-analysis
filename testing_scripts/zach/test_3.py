import datetime as dt

import pandas as pd
from src.orcasound_noise.pipeline.pipeline_3 import NoiseAnalysisPipeline
from src.orcasound_noise.utils import Hydrophone
import src.orcasound_noise.pipeline.val_utilities as util
import datetime as dt
from enum import Enum
from collections import namedtuple
import soundfile as sf
import numpy as np
import matplotlib.pyplot as plt
import csv


### MSDS Method
if __name__ == '__main__':
    pipeline = NoiseAnalysisPipeline(Hydrophone.PORT_TOWNSEND, pqt_folder='pqt', wav_folder='/Users/zach/Downloads/',
                                 delta_f=1, bands=None, delta_t=60)
    psd_path, broadband_path = pipeline.generate_parquet_file(dt.datetime(2023, 3, 22, 11), dt.datetime(2023, 3, 22, 12),
                                                          upload_to_s3=False)
    psd_df = pd.read_parquet(psd_path)
    row = psd_df.loc['2023-03-22 11:05:00']
    row.to_csv('/Users/zach/Desktop/row.txt', sep=' ', index=False)

### Val Method
    wavDir = '/Users/zach/Downloads/'
    dt_start = dt.datetime(2023, 3, 22, 11, 0)
    dt_stop = dt.datetime(2023, 3, 22, 11, 10)
    startSecs = 5 * 60 + 25  # 5 min and 25 seconds
    deltaT = 60  # one minute psd's

    calConstant = 0  # -35
    Nfft = 2048
    # Choose "Hamming" or "Blackman"
    fftWindow = "Blackman"
    fftWindow = "Hamming"

    wavFileList = [wavDir + 'rpi-port-townsend_2023_03_22_11_00_00.wav']

    outputCSVfile = wavDir + 'psdCSVfile.csv'
    wavFileSecs = 9e9  # 15 * 60  # set maximum number of seconds in single wav file

    with sf.SoundFile(wavFileList[0]) as f:
        samplerate = f.samplerate
    fhigh = samplerate / 2  # set high frequency cutoff at the Nyquist frequency
    Nsamples = int(deltaT * samplerate)

    freqPerHz, psdPerHz = util.calculatePSD(wavFileList[0], samplerate, startSecs, Nsamples, fhigh, Nfft, fftWindow,
                                            calConstant)

    with open(outputCSVfile, "w", newline="") as csvfile:  # Ensure consistent line endings
        writer = csv.writer(csvfile)
        # Write the array to the CSV file
        writer.writerows(psdPerHz.reshape(-1, 1))

'''
### Ben Method
# Returns ValueError: window is longer than input signal
# ben_data = pipeline.ben_wav_to_psd('/Users/zach/Downloads/rpi-port-townsend_2023_03_22_11_00_00.wav')
'''




