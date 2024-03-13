import pandas as pd
from orcasound_noise.pipeline.pipeline import NoiseAnalysisPipeline
from orcasound_noise.utils import Hydrophone
from orcasound_noise.pipeline.acoustic_util import plot_spec, plot_bb
import datetime as dt
import time

if __name__ == '__main__':
    ts = time.time()
    pipeline = NoiseAnalysisPipeline(Hydrophone.PORT_TOWNSEND,
                                     delta_f=1, bands=None,
                                     delta_t=60, mode='safe')

    psd_path, broadband_path = pipeline.generate_parquet_file(dt.datetime(2023, 3, 22, 12),
                                                              dt.datetime(2023, 3, 22, 13), upload_to_s3=False)

    psd_df = pd.read_parquet(psd_path)
    bb_df = pd.read_parquet(broadband_path)

    print("Execution Time", time.time()-ts)

    plot_spec(psd_df)

    plot_bb(bb_df)
