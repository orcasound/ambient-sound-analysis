import datetime as dt

from src.hydrophone import Hydrophone
from src.pipeline.pipeline import NoiseAnalysisPipeline


########## Analysis ######################
from src.analysis import NoiseAcccessor

## Create a Noise Accessor object
ac = NoiseAcccessor(Hydrophone.ORCASOUND_LAB)

# Create a dataframe 
default_df = ac.create_df(dt.datetime(2022, 1, 1), dt.datetime(2022, 1, 2))
print(default_df.head())

# Create a broadband dataframe
broadband_df = ac.create_df(dt.datetime(2022, 1, 1), dt.datetime(2022, 1, 2), delta_f="broadband")
print(broadband_df.head())

# Round the timestamps
rounded_df = ac.create_df(dt.datetime(2022, 1, 1), dt.datetime(2022, 1, 2), round_timestamps=True)
print(rounded_df.head())



