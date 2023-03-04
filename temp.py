import os
import seaborn as sns
import datetime as dt
from src.hydrophone import Hydrophone
from src.pipeline.pipeline import NoiseAnalysisPipeline
from src.pipeline.acoustic_util import spec_plot
from src.file_connector import S3FileConnector
from src.analysis import NoiseAcccessor
# from src import daily_noise
import matplotlib.pyplot as plt
import pandas as pd



#pipeline = NoiseAnalysisPipeline(Hydrophone.ORCASOUND_LAB, pqt_folder='pqt', delta_f=50, bands=3, delta_t=10)

#pipeline.generate_parquet_file_batch(dt.datetime(2023, 2, 2, 6), 3, dt.timedelta(hours=12))

# path = pipeline.generate_parquet_file(dt.datetime(2023, 2, 10, 5), dt.datetime(2023, 2, 10, 6), upload_to_s3=True)


# os.environ["AWS_ACCESS_KEY_ID"] = 'AKIAZN2WCXIFV5QME5EX'
# os.environ["AWS_SECRET_ACCESS_KEY"] = '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'

# fc = S3FileConnector(Hydrophone.SANDBOX)

# with open('pqt\\20230210T050000_20230210T150000_10s_500hz.parquet', 'rb') as file: 
#     result = fc.upload_file(file, dt.datetime(2023, 2, 10, 5), dt.datetime(2023, 2, 10, 15), 10, 500)
#     print(result)

# df = daily_noise.get_daily_df(dt.date(2023, 2, 2))
# df["63"].rolling(10).min().plot()

# summary_dfs = daily_noise.create_daily_noise_summary_df(dt.date(2023, 2, 1), 2)
# fig = daily_noise.plot_daily_noise(summary_dfs, ["63", "80"])

# plt.savefig('test_daily.png')

from src.analysis import NoiseAcccessor

ac = NoiseAcccessor(Hydrophone.ORCASOUND_LAB)
df = ac.create_df(dt.datetime(2023, 2, 1), dt.datetime(2023, 2, 2), delta_t=10, delta_f="3oct")
print(df.shape)

# t = dt.datetime(2022, 1, 1, 17, 59, 13, 198)
# print(NoiseAcccessor._round_seconds(t, 10))

# print(daily_noise.round_time(dt.time(1, 10, 2, 105), 10))