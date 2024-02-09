import pandas as pd
from src.orcasound_noise.pipeline.pipeline_3 import NoiseAnalysisPipeline
from src.orcasound_noise.utils import Hydrophone
import datetime as dt
import matplotlib.pyplot as plt

if __name__ == '__main__':
    pipeline = NoiseAnalysisPipeline(Hydrophone.PORT_TOWNSEND, pqt_folder='/Users/zach/Downloads/',
                                     wav_folder='/Users/zach/Downloads/', delta_f=1, bands=None, delta_t=60)
    psd_path, broadband_path = pipeline.generate_parquet_file(dt.datetime(2023, 3, 22, 0),
                                                              dt.datetime(2023, 3, 22, 23), upload_to_s3=False)
    bb_df = pd.read_parquet(broadband_path)
    plt.plot(bb_df)
    plt.show()

    '''
    psd_df = pd.read_parquet(psd_path)
    row = psd_df.loc['2023-03-22 11:05:00']
    plt.plot(row)
    plt.show()
    '''