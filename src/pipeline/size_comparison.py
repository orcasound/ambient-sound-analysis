import datetime as dt
import os

# Local imports
from src.pipeline import pipeline
import src.pipeline.acoustic_util as acoustic_util
import pandas as pd
import numpy as np


hops = [256, 512, 1024]
cols = [2 ** i for i in [10, 11, 12]]
pds_results = np.empty((len(hops), len(cols)), int)
broadband_results = pds_results.copy()

for i, hop_length in enumerate(hops):
    print("hop_length", hop_length)

    for j, n_fft in enumerate(cols):
        print("n_fft", n_fft)

        grams = [
            acoustic_util.wav_to_array(os.path.join('wav', f), hop_length=hop_length, n_fft=n_fft) 
            for f in os.listdir('wav') if os.path.isfile(os.path.join('wav', f))
        ]

        pds_frame = pd.concat(list(zip(*grams))[0])
        # pds_frame.columns = pds_frame.columns.map(str)

        broadband_frame = pd.concat(list(zip(*grams))[1])
        # broadband_frame.columns = broadband_frame.columns.map(str)

        pds_file = f'sample_pds_{hop_length}_{n_fft}.parquet'
        broadband_file = f'sample_broadband_{hop_length}_{n_fft}.parquet'

        pds_frame.to_parquet(pds_file)
        broadband_frame.to_parquet(broadband_file)

        pds_size = os.path.getsize(pds_file)
        broadband_size = os.path.getsize(broadband_file)
        
        print("size", pds_size)

        pds_results[i, j] = pds_size
        broadband_results[i, j] = broadband_size

print(pds_results)
print(broadband_results)