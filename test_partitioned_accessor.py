import sys
import datetime as dt
from pathlib import Path
sys.path.insert(0, 'src')

from orcasound_noise.analysis.partitioned_accessor import PartitionedAccessor
from orcasound_noise.utils.hydrophone import Hydrophone

accessor = PartitionedAccessor(Hydrophone.ORCASOUND_LAB_DATA)

start_time = dt.datetime(2026, 2, 1)
end_time = dt.datetime(2026, 2, 28, 23, 59, 59)

print("Fetching PSD data...")
psd_pl = accessor.get_time_range(start_time, end_time, psd=True)
print(f"PSD shape: {psd_pl.shape}")
print(psd_pl.head())

print("\nFetching broadband data...")
bb_pl = accessor.get_time_range(start_time, end_time, psd=False)
print(f"Broadband shape: {bb_pl.shape}")
print(bb_pl.head())

psd_out = Path("data/sound/psd/hydrophone=orcasound_lab/year=2026/month=02")
bb_out = Path("data/sound/broadband/hydrophone=orcasound_lab/year=2026/month=02")
psd_out.mkdir(parents=True, exist_ok=True)
bb_out.mkdir(parents=True, exist_ok=True)

print("\nSaving to disk...")
psd_pl.write_parquet(psd_out / "data.parquet")
bb_pl.write_parquet(bb_out / "data.parquet")
print(f"PSD saved to {psd_out}/data.parquet")
print(f"Broadband saved to {bb_out}/data.parquet")
