
from src import pipeline
from src import hydrophone
import datetime

orcasound_lab = hydrophone.Hydrophone.ORCASOUND_LAB
ship = pipeline.NoiseAnalysisPipeline(orcasound_lab, delta_f=10, delta_t=1, bands=3,)

start_time = datetime.datetime(2023,2,10,22,00,00)
end_time = datetime.datetime(2023,2,10,22,12,00)

file = ship.generate_parquet_file(start=start_time, end=end_time)