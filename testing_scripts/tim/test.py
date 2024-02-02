import datetime as dt

from src.orcasound_noise.analysis import NoiseAccessor
from src.orcasound_noise.utils import Hydrophone

# ac = NoiseAccessor(Hydrophone.ORCASOUND_LAB)
# df = ac.create_df(dt.datetime(2020, 1, 1), dt.datetime(2020, 1, 2), round_timestamps=True)op
# print(df)

import datetime as dt

from src.orcasound_noise.pipeline.pipeline import NoiseAnalysisPipeline
from src.orcasound_noise.utils import Hydrophone

pipeline = NoiseAnalysisPipeline(Hydrophone.PORT_TOWNSEND, pqt_folder='pqt', delta_f=1, bands=None, delta_t=1)
#print(pipeline)
psd_path, broadband_path = pipeline.generate_parquet_file(dt.datetime(2023, 3, 22, 11), dt.datetime(2023, 3, 22, 12), upload_to_s3=False)

#print(psd_path)
