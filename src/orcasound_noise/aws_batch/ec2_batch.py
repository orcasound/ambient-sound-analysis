from ..pipeline import pipeline
from ..utils import hydrophone

import datetime
import os
import glob

orcasound_lab = hydrophone.Hydrophone.ORCASOUND_LAB
startyear = 2020
startmonth = 2
endyear = 2020
endmonth = 3
x = 1
dates = [datetime.datetime(m//12, m%12+1, 1, 00, 00, 00) for m in range (startyear*12+startmonth-1, endyear*12+endmonth)]
every_x_months = dates[0::x]
if every_x_months[-1] != dates[-1]:
    every_x_months.append(dates [-1])
for index, month in enumerate (every_x_months):
    if index + 1 < len (every_x_months):
        start_time = month
        end_time = every_x_months[index+1]
        ship = pipeline.NoiseAnalysisPipeline(orcasound_lab, delta_f=10, delta_t=1, bands=3, wav_folder="wav_folder", pqt_folder="pqt_folder")
        print('generating parquet for dates {} to {}.'.format(start_time, end_time))
        file = ship.generate_parquet_file(start=start_time, end=end_time, upload_to_s3=True)
        del ship
        files = glob.glob('wav_folder/*')
        for f in files:
            os.remove(f)