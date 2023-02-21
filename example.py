import datetime as dt
from src.hydrophone import Hydrophone
from src.pipeline import NoiseAnalysisPipeline

# Create Pipeline
pipeline = NoiseAnalysisPipeline(Hydrophone.ORCASOUND_LAB, pqt_folder='pqt', delta_f=1000, delta_t=1)

# Generate Parquet File
pipeline.generate_parquet_file(dt.date(2022, 11, 5), dt.date(2022, 11, 6))

# Generate Week of data
pipeline.generate_parquet_file_batch(dt.date(2022, 10, 1), 7, dt.timedelta(days=1))



