import datetime as dt

import librosa
import pandas as pd
import numpy as np

from src.orcasound_noise.pipeline.pipeline import NoiseAnalysisPipeline
from src.orcasound_noise.utils import Hydrophone


pipeline = NoiseAnalysisPipeline(Hydrophone.PORT_TOWNSEND, pqt_folder='pqt', delta_f=1, bands=None, delta_t=1)
psd_path, broadband_path = pipeline.generate_parquet_file(dt.datetime(2023, 3, 22, 11), dt.datetime(2023, 3, 22, 12), upload_to_s3=False)

psd_df = pd.read_parquet(psd_path)
psd_df2 = psd_df.copy()

'''
psd_df2.to_csv('/Users/zach/Desktop/psd_df2.csv', index=True)
psd_df2 = pd.read_csv('/Users/zach/Desktop/psd_df2.csv').set_index('Unnamed: 0')
cols = psd_df2.columns
ind = psd_df2.index
test = psd_df2.to_numpy()
test = librosa.db_to_amplitude(test)
test = pd.DataFrame(test, columns=cols)
test['ind'] = ind
test = test.set_index(pd.DatetimeIndex(test['ind']))
test = test.resample('1Min').mean()
test = test.to_numpy()
test = librosa.amplitude_to_db(np.abs(test), ref=np.max)
print(test)
'''

psd_df2 = psd_df2.resample('1Min').mean()
row = psd_df2.loc['2023-03-22 11:05:00']
row.to_csv('/Users/zach/Desktop/row.txt', sep=' ', index=False)
