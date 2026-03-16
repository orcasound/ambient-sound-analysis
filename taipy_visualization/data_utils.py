# import pandas as pd
# import polars as pl
# import datetime as dt
# import geopandas as gpd
# from datetime import datetime, date, time, timedelta
# from dotenv import load_dotenv
# import requests
# import pytz
# from zoneinfo import ZoneInfo
# import json
# from typing import List, Tuple
# from orcasound_noise.utils.hydrophone import Hydrophone
# from orcasound_noise.analysis.partitioned_accessor import PartitionedAccessor

# load_dotenv()

# s3_path = "s3://acoustic-sandbox/ambient-sound-analysis/data_2.0/psd/"

# LOCAL_TZ = ZoneInfo("America/Los_Angeles")
# UTC_TZ = ZoneInfo("UTC")


# # def _day_prefix(hydrophone, year, month, day):
# #     return (
# #         "s3://acoustic-sandbox/ambient-sound-analysis/data_2.0/psd/"
# #         f"hydrophone={hydrophone}/year={year}/month={int(month):02d}/day={int(day):02d}/"
# #     )






# def get_available_hours_map(month, day, hydrophone_enum, year):
#     """
#     Maps the available hours in S3 for a strict UTC day.
#     """
#     # Treat the incoming date as strict UTC boundaries
#     utc_start = datetime(year, month, day, 0, 0, 0)
#     utc_end = utc_start + timedelta(days=1)

#     try:

#         accessor = PartitionedAccessor(hydrophone_enum, utc_start, utc_end)
#         psd_lazy, _ = accessor.get_dataframes(lazy=True)

#         # Accessor returns UTC-naive timestamps. Since we want UTC, 
#         # we can just extract the hour directly without timezone conversions.
#         df_hours = (
#             psd_lazy
#             .select(
#                 pl.col("__index_level_0__")
#                 .dt.hour()
#                 .alias("utc_hour")
#             )
#             .unique()
#             .sort("utc_hour")
#             .collect()
#         )

#         if df_hours.is_empty():
#             return []

#         hours = df_hours.get_column("utc_hour").to_list()
#         return [f"{h:02d}:00 to {(h + 1) % 24:02d}:00" for h in hours]

#     except Exception as e:
#         print(f"Accessor failed to map hours: {e}")
#         return []
    





# def load_ship_data(shp_path):
#     """
#     Loads Radar ship tracks, filters by validity, and formats columns 
#     for the Plotly spectrogram overlay.
#     """
#     try:
#         # Load the shapefile
#         gdf = gpd.read_file(shp_path)
        
#         gdf['entry_time'] = pd.to_datetime(gdf['sdate'] + ' ' + gdf['stime'])
#         gdf['exit_time'] = pd.to_datetime(gdf['ldate'] + ' ' + gdf['ltime'])
        
#         # Filter for valid tracks (Confidence >= 0.5 or has AIS association)
#         gdf['valid'] = (gdf['confidence'] >= 0.5) | (gdf['assoc_id'].notna())
#         gdf = gdf[gdf['valid'] & gdf['geometry'].notna()].sort_values('entry_time')
        
#         # Rename distance to closest_approach_km
#         if 'distance' in gdf.columns:
#             gdf = gdf.rename(columns={'distance': 'closest_approach_km'})
            
#         # Convert to standard Pandas DataFrame (drop geometry)
#         df = pd.DataFrame(gdf.drop(columns=['geometry'], errors='ignore'))
        
#         return df
        
#     except Exception as e:
#         print(f"Error loading Shapefile: {e}")
#         return pd.DataFrame()





# def fetch_acoustic_data(date, start_time, end_time, hydrophone="orcasound_lab"):
#     year = date.year
#     month = date.month
#     day = date.day
    
#     # Format the prefix carefully to match S3 hive partitioning
#     # month/day usually need leading zeros (e.g., month=02, day=07)
#     prefix = f"s3://acoustic-sandbox/ambient-sound-analysis/data_2.0/psd/hydrophone={hydrophone}/year={year}/month={month:02d}/day={day:02d}/"
    
#     try:
#         # We try to scan the path. If the folder is missing, Polars throws the error you saw.
#         psd_df = pl.scan_parquet(
#             prefix,
#             hive_partitioning=True,
#             storage_options={'aws_region': 'us-west-2'}
#         )

#         start_naive = start_time.replace(tzinfo=None)
#         end_naive = end_time.replace(tzinfo=None)

#         pq_files = (
#             psd_df
#             .filter(pl.col("__index_level_0__").is_between(start_naive, end_naive))
#             .collect()
#         )
#         return pq_files

#     except Exception as e:
#         # This catches "expanded paths were empty" and returns an empty DF gracefully
#         print(f"--- No data found for {year}-{month:02d}-{day:02d} in S3 ---")
#         return pl.DataFrame()






# # --------------------------------------------------------------------------------------------------- #
# # ---------------------------------------- BOUT API Section ----------------------------------------- #
# # --------------------- Currently not being used. Shifted to OrcaHello for richer data -------------- #
# # --------------------------------------------------------------------------------------------------- #

# # def _ensure_utc(ts, assumed_local_tz=LOCAL_TZ):
    
# #     if isinstance(ts, date) and not isinstance(ts, datetime):
# #         ts = datetime.combine(ts, time.min)

# #     ts = pd.Timestamp(ts)
    
# #     if ts.tzinfo is None:
# #         ts = ts.tz_localize(assumed_local_tz)
# #     else:
# #         ts = ts.tz_convert(assumed_local_tz)
        
# #     return ts.tz_convert(UTC_TZ)

# # def fetch_bout_data(start_time, end_time, feed_name="Orcasound Lab", feed_id="feed_02u8r4ELz2xkCjPTc4yLWE"):
# #     """
# #     Fetches bouts and their corresponding detections for a specific feed and time window.
    
# #     Args:
# #         start_time (datetime): Timezone-aware UTC datetime for the start of the window.
# #         end_time (datetime): Timezone-aware UTC datetime for the end of the window.
# #         feed_name (str): Human-readable name of the feed (for logging/reference).
# #         feed_id (str): Orcasound feed ID.
        
# #     Returns:
# #         list: A list of dictionaries containing bout start/end times and their specific detections.
# #     """

# #     start_time = _ensure_utc(start_time)
# #     end_time = _ensure_utc(end_time)

# #     base_url = "https://live.orcasound.net"
# #     headers = {"Accept": "application/vnd.api+json"}
    
# #     # Inner helper to handle the JSON:API pagination and flattening automatically
# #     def _fetch_all(endpoint, max_pages=100):
# #         session = requests.Session()
# #         data = []
# #         url = f"{base_url}{endpoint}"
# #         params = {"page[limit]": 250, "feed_id": feed_id}
        
# #         pages_fetched = 0
# #         while url and pages_fetched < max_pages:
# #             response = session.get(url, headers=headers, params=params, timeout=30)
# #             response.raise_for_status()
# #             payload = response.json()
            
# #             # Flatten the JSON:API structure (combine 'id' and 'attributes')
# #             for item in payload.get("data", []):
# #                 record = {"id": item.get("id")}
# #                 record.update(item.get("attributes", {}))
# #                 data.append(record)
            
# #             # Handle pagination
# #             url = payload.get("links", {}).get("next")
# #             params = None
# #             pages_fetched += 1
            
# #         return pd.DataFrame(data)

# #     # Fetch and format all bouts
# #     bouts_df = _fetch_all("/api/json/bouts")
# #     if bouts_df.empty or "start_time" not in bouts_df.columns:
# #         return []

# #     bouts_df["start_time"] = pd.to_datetime(bouts_df["start_time"], utc=True, errors="coerce")
# #     bouts_df["end_time"] = pd.to_datetime(bouts_df["end_time"], utc=True, errors="coerce")
# #     bouts_df = bouts_df.dropna(subset=["start_time", "end_time"])
    
# #     # Filter bouts_df to get only those bouts whose feed_id matches the one we provide (default is orcasound lab)
# #     if "feed_id" in bouts_df.columns:
# #         bouts_df = bouts_df[bouts_df["feed_id"].astype(str) == str(feed_id)]
        
# #     # Keep bouts that overlap the requested window
# #     bouts_df = bouts_df[(bouts_df["end_time"] > start_time) & (bouts_df["start_time"] < end_time)]

# #     # Fetch and format all detections
# #     dets_df = _fetch_all("/api/json/detections")

# #     if not dets_df.empty and "timestamp" in dets_df.columns:
# #         dets_df["timestamp"] = pd.to_datetime(dets_df["timestamp"], utc=True, errors="coerce")
# #         dets_df = dets_df.dropna(subset=["timestamp"])
# #         if "feed_id" in dets_df.columns:
# #             dets_df = dets_df[dets_df["feed_id"].astype(str) == str(feed_id)]

# #     # Build the final structured output
# #     result = []
# #     for _, bout in bouts_df.iterrows():
# #         b_start = bout["start_time"]
# #         b_end = bout["end_time"]
        
# #         bout_data = {
# #             "bout_start": b_start.isoformat(),
# #             "bout_end": b_end.isoformat(),
# #             "detections": []
# #         }
        
# #         # Find detections that fall strictly within this bout's timeframe
# #         if not dets_df.empty:
# #             mask = (dets_df["timestamp"] >= b_start) & (dets_df["timestamp"] <= b_end)
# #             bout_dets = dets_df[mask]
            
# #             for _, det in bout_dets.iterrows():
# #                 bout_data["detections"].append({
# #                     "timestamp": det["timestamp"].isoformat(),
# #                     "description": det.get("description", ""),
# #                     "source": det.get("source", ""),
# #                     "category": det.get("category", "")
# #                 })
                
# #         result.append(bout_data)
        
# #     return result


# # def fetch_detections(start_time, end_time, location="Orcasound Lab"):
# #     base_url = "https://aifororcasdetections.azurewebsites.net/api/detections"
    
# #     # Back to the exact format the API docs specify
# #     date_from = start_time.strftime("%m/%d/%Y")
# #     date_to = end_time.strftime("%m/%d/%Y")
    
# #     params = {
# #         "Page": 1,
# #         "SortBy": "timestamp",
# #         "SortOrder": "desc",
# #         "Timeframe": "range",
# #         "DateFrom": date_from,
# #         "DateTo": date_to,
# #         "Location": location, 
# #         "HydrophoneId": "rpi_orcasound_lab"
# #     }
    
# #     try:
# #         response = requests.get(base_url, params=params, timeout=15)
        
# #         response.raise_for_status()
        
# #         if not response.text.strip():
# #             print("API returned an empty response instead of JSON.")
# #             return []
            
# #         data = response.json()
        
# #         if isinstance(data, list):
# #             return data
# #         else:
# #             return data.get("items", [])
            
# #     except Exception as e:
# #         # Print the raw text if it fails to parse so we can read the error message
# #         if 'response' in locals() and response is not None:
# #             print(f"Raw API Response: {response.text}")
# #         print(f"Error fetching Azure data: {e}")
# #         return []

# # --------------------------------------------------------------------------------------------------- #
# # --------------------------------------- End of Bout API Section ----------------------------------- #
# # --------------------------------------------------------------------------------------------------- #






# # --------------------------------------------------------------------------------------------------- #
# # --------------------------------------- OrcaHello Section ----------------------------------------- #
# # --------------------------------------------------------------------------------------------------- #

# def fetch_detections(start_time, end_time, location="Orcasound Lab"):
#     base_url = "https://aifororcasdetections.azurewebsites.net/api/detections"
    
#     date_from = start_time.strftime("%m/%d/%Y")
#     date_to = end_time.strftime("%m/%d/%Y")
    
#     all_items = []
#     page = 1
    
#     while True:
#         params = {
#             "Page": page,
#             "RecordsPerPage": 50,  # <-- Adjusted to match the API's hard cap
#             "SortBy": "timestamp",
#             "SortOrder": "desc",
#             "Timeframe": "range",
#             "DateFrom": date_from,
#             "DateTo": date_to,
#             "Location": location, 
#             "HydrophoneId": "rpi_orcasound_lab"
#         }
        
#         try:
#             response = requests.get(base_url, params=params, timeout=15)
#             response.raise_for_status()
            
#             if not response.text.strip():
#                 break
                
#             data = response.json()
#             items = data if isinstance(data, list) else data.get("items", [])
            
#             if not items:
#                 break # Exit loop if no more items are found
                
#             all_items.extend(items)
            
#             # If we get fewer than 50 items, we know we've hit the final page
#             if len(items) < 50:
#                 break
                
#             page += 1 # Move to the next page of results
            
#         except Exception as e:
#             print(f"Error fetching Azure data on Page {page}: {e}")
#             break

#     # print(f"Fetched {len(all_items)} for the duration \n {start_time} to {end_time}")        
#     return all_items

# # --------------------------------------------------------------------------------------------------- #
# # -------------------------------- End of OrcaHello Section ----------------------------------------- #
# # --------------------------------------------------------------------------------------------------- #


# # --------------------------------------------------------------------------------------------------- #
# # --------------------------------------- Ship Leaderboard Helpers ---------------------------------- #
# # --------------------------------------------------------------------------------------------------- #

# def _to_utc_naive(ts):
#     """
#     Convert any pandas/python timestamp to UTC-naive datetime,
#     because the parquet timestamps are being handled as UTC-naive.
#     """
#     ts = pd.Timestamp(ts)
#     if ts.tzinfo is None:
#         ts = ts.tz_localize("UTC")
#     else:
#         ts = ts.tz_convert("UTC")
#     return ts.tz_localize(None).to_pydatetime()






# def fetch_psd_window(hydrophone_enum: Hydrophone, start_time, end_time):
#     """
#     Fetch PSD rows for an arbitrary UTC window.
#     """
#     start_naive = _to_utc_naive(start_time)
#     end_naive = _to_utc_naive(end_time)

#     base = f"s3://{hydrophone_enum.value.save_bucket}/{hydrophone_enum.value.save_folder}/psd/hydrophone={hydrophone_enum.value.name}"
    
#     current_date = start_naive.date()
#     end_date = end_naive.date()
    
#     valid_scans = []
    
#     # Find which exact day paths actually exist
#     while current_date <= end_date:
#         path = f"{base}/year={current_date.year}/month={current_date.month:02d}/day={current_date.day:02d}/*.parquet"
        
#         try:
#             lf = pl.scan_parquet(path, storage_options={"aws_region": "us-west-2"})
#             valid_scans.append(lf)
        
#         except Exception:
#             pass
        
#         current_date += timedelta(days=1)
        
#     # If no valid files were found, exit early to prevent render crashes
#     if not valid_scans:
#         print(f"[PSD WINDOW] No data exists in S3 between {start_naive} and {end_naive}")
#         return pl.DataFrame()
        
#     # Concatenate the valid days and filter to the exact requested hour
#     try:
#         return (
#             pl.concat(valid_scans)
#             .filter(
#                 (pl.col("__index_level_0__") >= start_naive) &
#                 (pl.col("__index_level_0__") < end_naive)
#             )
#             .sort("__index_level_0__")
#             .collect()
#         )
#     except Exception as e:
#         print(f"[PSD WINDOW] Failed to process combined PSD data: {e}")
#         return pl.DataFrame()


import pandas as pd
import polars as pl
import geopandas as gpd
import requests

from datetime import datetime, timedelta, date
from dotenv import load_dotenv

from orcasound_noise.analysis.partitioned_accessor import PartitionedAccessor
from orcasound_noise.utils.hydrophone import Hydrophone
from dashboard_utils import localize_series_to_pacific, parse_source_timestamp


load_dotenv()

MIGRATION_START_DATE = date(2026, 3, 3)


def _to_pst_naive(ts):
    """
    Convert any timestamp into PST naive datetime for PartitionedAccessor.
    """
    ts = parse_source_timestamp(ts)
    return ts.to_pydatetime()






def get_available_hours_map(month, day, hydrophone_enum, year):
    selected_day = date(year, month, day)
    if selected_day < MIGRATION_START_DATE:
        return []

    pst_start = datetime(year, month, day, 0, 0, 0)
    pst_end_exclusive = pst_start + timedelta(days=1)

    try:
        accessor = PartitionedAccessor(
            hydrophone_enum,
            pst_start,
            pst_end_exclusive - timedelta(microseconds=1)
        )
        psd_lazy, _ = accessor.get_dataframes(lazy=True)

        df_hours = (
            psd_lazy
            .select(pl.col("ind").dt.hour().alias("pst_hour"))
            .unique()
            .sort("pst_hour")
            .collect()
        )

        if df_hours.is_empty():
            return []

        hours = df_hours.get_column("pst_hour").to_list()
        return [f"{h:02d}:00 to {(h + 1) % 24:02d}:00" for h in hours]

    except Exception as e:
        print(f"Accessor failed to map hours: {e}")
        return []






def load_ship_data(shp_path):
    try:
        gdf = gpd.read_file(shp_path)

        entry_time = pd.to_datetime(gdf["sdate"] + " " + gdf["stime"], errors="coerce")
        exit_time = pd.to_datetime(gdf["ldate"] + " " + gdf["ltime"], errors="coerce")

        gdf["entry_time"] = localize_series_to_pacific(entry_time)
        gdf["exit_time"] = localize_series_to_pacific(exit_time)

        gdf["valid"] = (gdf["confidence"] >= 0.5) | (gdf["assoc_id"].notna())
        gdf = gdf[gdf["valid"] & gdf["geometry"].notna()].sort_values("entry_time")

        if "distance" in gdf.columns:
            gdf = gdf.rename(columns={"distance": "closest_approach_km"})

        return pd.DataFrame(gdf.drop(columns=["geometry"], errors="ignore"))

    except Exception as e:
        print(f"Error loading Shapefile: {e}")
        return pd.DataFrame()






def fetch_psd_window(hydrophone_enum: Hydrophone, start_time, end_time):
    start_naive = _to_pst_naive(start_time)
    end_naive = _to_pst_naive(end_time)

    if end_naive <= start_naive or start_naive.date() < MIGRATION_START_DATE:
        return pl.DataFrame()

    try:
        accessor = PartitionedAccessor(
            hydrophone_enum,
            start_naive,
            end_naive - timedelta(microseconds=1)
        )
        pl_psd, _ = accessor.get_dataframes(lazy=True)
        return pl_psd.collect()

    except Exception as e:
        print(f"[PSD WINDOW] Failed to fetch PSD window: {e}")
        return pl.DataFrame()





def fetch_bb_window(hydrophone_enum: Hydrophone, start_time, end_time):
    start_naive = _to_pst_naive(start_time)
    end_naive = _to_pst_naive(end_time)

    if end_naive <= start_naive or start_naive.date() < MIGRATION_START_DATE:
        return pl.DataFrame()

    try:
        accessor = PartitionedAccessor(
            hydrophone_enum,
            start_naive,
            end_naive - timedelta(microseconds=1)
        )
        _, pl_bb = accessor.get_dataframes(lazy=True)
        return pl_bb.collect()

    except Exception as e:
        print(f"[BB WINDOW] Failed to fetch broadband window: {e}")
        return pl.DataFrame()






def fetch_acoustic_data(selected_date, start_time, end_time, hydrophone=Hydrophone.ORCASOUND_LAB):
    """
    Optional wrapper for PSD only.
    """
    hydrophone_enum = hydrophone if isinstance(hydrophone, Hydrophone) else Hydrophone.ORCASOUND_LAB
    return fetch_psd_window(hydrophone_enum, start_time, end_time)







def fetch_detections(start_time, end_time, location="Orcasound Lab"):
    """
    Fetch OrcaHello detections using Pacific-local date boundaries.
    """
    base_url = "https://aifororcasdetections.azurewebsites.net/api/detections"

    date_from = start_time.strftime("%m/%d/%Y")
    date_to = end_time.strftime("%m/%d/%Y")

    all_items = []
    page = 1

    while True:
        params = {
            "Page": page,
            "RecordsPerPage": 50,
            "SortBy": "timestamp",
            "SortOrder": "desc",
            "Timeframe": "range",
            "DateFrom": date_from,
            "DateTo": date_to,
            "Location": location,
            "HydrophoneId": "rpi_orcasound_lab"
        }

        try:
            response = requests.get(base_url, params=params, timeout=15)
            response.raise_for_status()

            if not response.text.strip():
                break

            data = response.json()
            items = data if isinstance(data, list) else data.get("items", [])

            if not items:
                break

            all_items.extend(items)

            if len(items) < 50:
                break

            page += 1

        except Exception as e:
            print(f"Error fetching OrcaHello data on page {page}: {e}")
            break

    return all_items
