import pandas as pd
from orcasound_noise.pipeline.pipeline import NoiseAnalysisPipeline
from orcasound_noise.utils import Hydrophone
from orcasound_noise.pipeline.acoustic_util import plot_spec
import datetime as dt
import matplotlib.pyplot as plt
import time

if __name__ == '__main__':
    ts = time.time()
    pipeline = NoiseAnalysisPipeline(Hydrophone.PORT_TOWNSEND, 
                                     delta_f=1, bands=None,
                                     delta_t=60, mode='safe')

    psd_path, broadband_path = pipeline.generate_parquet_file(dt.datetime(2023, 3, 22, 11),
                                                              dt.datetime(2023, 3, 22, 12), upload_to_s3=False)

    bb_df = pd.read_parquet(broadband_path)
    psd_df = pd.read_parquet(psd_path)
    print("#"*10, 'Shape: ', psd_df.shape)
    print("Execution Time", time.time()-ts)
    # plot_spec(psd_df)

    plt.plot(bb_df)
    plt.show()

    ########## Shape:  (51, 24001)
