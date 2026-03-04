# Ship Metrics

In the ship_metrics.py, the ShipMetricsCalculator allows users to calculate ship related metrics, including speed, duration, isolation flags, acoustic metrics, and distances to hydrophones. The README will introduce the definition and usage of the metrics.

## Metrics

## Ship Passage & Acoustic Metrics Data Dictionary

| Column Name  | Description | Availability |
|--------------|------------|------------|
| `id_track`  | unique id for vessel tracking ||
| `s_timestamp` | Local timestamp of first detection along track ||
| `l_timestamp` | Local timestamp of last detection along track ||
| `duration` | Time spent in designated zone of interest (seconds) ||
| `avg_speed` | Average speed ||
| `max_speed` | Maximum speed ||
| `min_speed` | Minimum speed ||
| `distance` | Total distance target traveled along track (kilometers) ||
| `curviness` | Total distance along track divided by distance between first and last detection ||
| `confidence` | Target confidence score (0–1) reflecting likelihood that a target is a true vessel and not a false detection (if available at site) ||
| `mmsi` | Ship ID (Maritime Mobile Service Identity) | Available if the vessel tracking is associated to an AIS tracking id  |
| `name` | Name of the ship | Available if the vessel tracking is associated to an AIS tracking id  |
| `draft` | Distance between water surface and lowest point on vessel reported in AIS data (meters) | Available if the vessel tracking is associated to an AIS tracking id  |
| `type id` | Ship type id | Available if the vessel tracking is associated to an AIS tracking id  |
| `type` | Ship type | Available if the vessel tracking is associated to an AIS tracking id  |
| `is_isolated` | `True` if the `id_track` is the only tracked vessel between `s_timestamp` and `l_timestamp`, else `False` |
| `bb_qXX` | The XXth percentile of the broadband between `s_timestamp` and `l_timestamp` |
| `comm_bb_qXX` | The XXth percentile of the communication frequency (1000-6000 Hz) broadband between `s_timestamp` and `l_timestamp` |
| `ship_bb_qXX` | The XXth percentile of the ship frequency  (10-200 Hz) broadband between `s_timestamp` and `l_timestamp` |
| `bb_lsr_qXX` | The XXth percentile of the listening space reduction to the broadband between `s_datetime` and `l_datetime` |
| `comm_bb_lsr_qXX` | The XXth percentile of the listening space reduction to the communication frequency (1000-6000 Hz) broadband between `s_datetime` and `l_datetime` |
| `ship_bb_lsr_qXX` | The XXth percentile of the listening space reduction to the ship frequency (10-200 Hz) broadband between `s_datetime` and `l_datetime` |
| `min_dist` | Minimum distance to the hydrophone location between `s_datetime` and `l_datetime`  |
| `year` | The XXth percentile of the listening space reduction to the communication frequency broadband between `s_datetime` and `l_datetime` |
| `month` | The XXth percentile of the listening space reduction to the ship frequency broadband between `s_datetime` and `l_datetime` |
| `day` | Minimum distance to the hydrophone location between `s_datetime` and `l_datetime`  |

# Example Usage

load tracking data. One can skip this part if having M2 data in hand
```{python}
# User will need credential to access M2 data.
from dotenv import load_dotenv
load_dotenv()

ship_pipeline = ShipAnalysisPipeline()
lf_ais, lf_radar = ship_pipeline.get_raw_data_from_m2() # It will load the latest 7 days of tracking data.
```

Get the relevent time of the passages
```{python}
# `start` and `end` should be the earliest and latest date in the vessel tracking data
start, end = ship_pipeline.start_date, ship_pipeline.end_date 
```

Load the relevent sound data. One can skip this part if having relevent sound data in hand
```{python}
start = dt.datetime.combine(start, dt.time.min) # earliest time in the date
end = dt.datetime.combine(end, dt.time.max) # latest time in the date

ac_orcalab = PartitionedAccessor(Hydrophone.ORCASOUND_LAB, start, end)
lf_psd, lf_bb = ac_orcalab.get_dataframes(lazy=True)
```

Create a Calculator with radar tracking, ais tracking, and broadband data. All the input data should be `polars.LazyFrame`

```{python}
ship_metrics_cal = ShipMetricsCalculator(lf_radar, lf_ais, lf_bb)
pl_ship_metrics = ship_metrics_cal.get_all_ship_metrics()
```