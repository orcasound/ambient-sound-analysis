import datetime as dt

# Local imports
from orca_hls_utils.DateRangeHLSStream import DateRangeHLSStream
from src import pipeline
import pandas as pd



# Create spectrograms and visualize one
grams = pipeline.ts_to_array(
    dt.date(2022, 11, 5),
    dt.date(2022, 11, 6),
    'wav', max_files=60
)
pds_frame = pd.concat(list(zip(*grams))[0])
# pds_frame.columns = pds_frame.columns.map(str)

broadband_frame = pd.concat(list(zip(*grams))[1])
# broadband_frame.columns = broadband_frame.columns.map(str)

pds_frame.to_parquet('sample_pds.parquet')
broadband_frame.to_parquet('sample_broadband.parquet')