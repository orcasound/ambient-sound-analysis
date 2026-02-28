import pandas as pd
import polars as pl
import datetime as dt
import geopandas as gpd
from datetime import datetime, date, time
from dotenv import load_dotenv
import requests
import pytz
from zoneinfo import ZoneInfo


load_dotenv()

s3_path = "s3://acoustic-sandbox/ambient-sound-analysis/data_2.0/psd/"

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
UTC_TZ = ZoneInfo("UTC")


def _day_prefix(hydrophone, year, month, day):
    return (
        "s3://acoustic-sandbox/ambient-sound-analysis/data_2.0/psd/"
        f"hydrophone={hydrophone}/year={year}/month={int(month):02d}/day={int(day):02d}/"
    )


def get_available_hours_map(month_str, day_str, hydrophone, year):
    
    month = int(month_str)
    day = int(day_str)
    year = int(year)

    day_prefix = _day_prefix(hydrophone, year, month, day)

    try:
        
        lf = pl.scan_parquet(
            day_prefix, 
            hive_partitioning=True,
            storage_options={'aws_region': 'us-west-2'}
            )
        
        start_time = dt.datetime(year, month, day, 0, 0, 0)
        end_time = dt.datetime(year, month, day, 23, 0, 0)

        hours = (
            lf.select(
                pl.col("__index_level_0__").dt.hour().alias("hour")
            )
            .filter(
                pl.col("hour").is_between(start_time.hour, end_time.hour)
            )
            .unique()
            .sort("hour")
            .collect()
            .get_column("hour")
            .to_list()
        )

        formatted_hours = [f"{h:02d}:00 to {h+1:02d}:00" for h in hours]
        
        return formatted_hours

    except Exception as e:
        print(f"An error occured\n: {e}")
        return []
    
def load_ship_data(shp_path):
    """
    Loads Radar ship tracks, filters by validity, and formats columns 
    for the Plotly spectrogram overlay.
    """
    try:
        # Load the shapefile
        gdf = gpd.read_file(shp_path)
        
        gdf['entry_time'] = pd.to_datetime(gdf['sdate'] + ' ' + gdf['stime'])
        gdf['exit_time'] = pd.to_datetime(gdf['ldate'] + ' ' + gdf['ltime'])
        
        # Filter for valid tracks (Confidence >= 0.5 or has AIS association)
        gdf['valid'] = (gdf['confidence'] >= 0.5) | (gdf['assoc_id'].notna())
        gdf = gdf[gdf['valid'] & gdf['geometry'].notna()].sort_values('entry_time')
        
        # Rename distance to closest_approach_km
        if 'distance' in gdf.columns:
            gdf = gdf.rename(columns={'distance': 'closest_approach_km'})
            
        # Convert to standard Pandas DataFrame (drop geometry)
        df = pd.DataFrame(gdf.drop(columns=['geometry'], errors='ignore'))
        
        return df
        
    except Exception as e:
        print(f"Error loading Shapefile: {e}")
        return pd.DataFrame()

def fetch_acoustic_data(date, start_time, end_time, hydrophone="orcasound_lab"):
    """
    This function will fetch all the parquet files for a given day within the start and end time range. 
    These will then be sorted by index, concatenated, and sent as a dictionary
    """
    year = date.year
    month = date.month
    day = date.day
    prefix = _day_prefix(hydrophone, year, month, day)
    
    psd_df = pl.scan_parquet(
        prefix,
        hive_partitioning=True,
        storage_options={'aws_region': 'us-west-2'}
        )

    try:
        pq_files = (
            psd_df
            .filter(
                (pl.col("__index_level_0__").is_between(start_time, end_time))
            ).collect()
        )
        return pq_files
    
    except Exception:
        print("Could not find data in the selected time range")
        return pl.DataFrame()

# -------------------------- BOUT API Section ----------------------------------------- #

def _ensure_utc(ts, assumed_local_tz=LOCAL_TZ):
    
    if isinstance(ts, date) and not isinstance(ts, datetime):
        ts = datetime.combine(ts, time.min)

    ts = pd.Timestamp(ts)
    
    if ts.tzinfo is None:
        ts = ts.tz_localize(assumed_local_tz)
    else:
        ts = ts.tz_convert(assumed_local_tz)
        
    return ts.tz_convert(UTC_TZ)

def fetch_bout_data(start_time, end_time, feed_name="Orcasound Lab", feed_id="feed_02u8r4ELz2xkCjPTc4yLWE"):
    """
    Fetches bouts and their corresponding detections for a specific feed and time window.
    
    Args:
        start_time (datetime): Timezone-aware UTC datetime for the start of the window.
        end_time (datetime): Timezone-aware UTC datetime for the end of the window.
        feed_name (str): Human-readable name of the feed (for logging/reference).
        feed_id (str): Orcasound feed ID.
        
    Returns:
        list: A list of dictionaries containing bout start/end times and their specific detections.
    """

    start_time = _ensure_utc(start_time)
    end_time = _ensure_utc(end_time)

    base_url = "https://live.orcasound.net"
    headers = {"Accept": "application/vnd.api+json"}
    
    # Inner helper to handle the JSON:API pagination and flattening automatically
    def _fetch_all(endpoint, max_pages=100):
        session = requests.Session()
        data = []
        url = f"{base_url}{endpoint}"
        params = {"page[limit]": 250, "feed_id": feed_id}
        
        pages_fetched = 0
        while url and pages_fetched < max_pages:
            response = session.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            
            # Flatten the JSON:API structure (combine 'id' and 'attributes')
            for item in payload.get("data", []):
                record = {"id": item.get("id")}
                record.update(item.get("attributes", {}))
                data.append(record)
            
            # Handle pagination
            url = payload.get("links", {}).get("next")
            params = None
            pages_fetched += 1
            
        return pd.DataFrame(data)

    # Fetch and format all bouts
    bouts_df = _fetch_all("/api/json/bouts")
    if bouts_df.empty or "start_time" not in bouts_df.columns:
        return []

    bouts_df["start_time"] = pd.to_datetime(bouts_df["start_time"], utc=True, errors="coerce")
    bouts_df["end_time"] = pd.to_datetime(bouts_df["end_time"], utc=True, errors="coerce")
    bouts_df = bouts_df.dropna(subset=["start_time", "end_time"])
    
    # Filter bouts_df to get only those bouts whose feed_id matches the one we provide (default is orcasound lab)
    if "feed_id" in bouts_df.columns:
        bouts_df = bouts_df[bouts_df["feed_id"].astype(str) == str(feed_id)]
        
    # Keep bouts that overlap the requested window
    bouts_df = bouts_df[(bouts_df["end_time"] > start_time) & (bouts_df["start_time"] < end_time)]

    # Fetch and format all detections
    dets_df = _fetch_all("/api/json/detections")

    if not dets_df.empty and "timestamp" in dets_df.columns:
        dets_df["timestamp"] = pd.to_datetime(dets_df["timestamp"], utc=True, errors="coerce")
        dets_df = dets_df.dropna(subset=["timestamp"])
        if "feed_id" in dets_df.columns:
            dets_df = dets_df[dets_df["feed_id"].astype(str) == str(feed_id)]

    # Build the final structured output
    result = []
    for _, bout in bouts_df.iterrows():
        b_start = bout["start_time"]
        b_end = bout["end_time"]
        
        bout_data = {
            "bout_start": b_start.isoformat(),
            "bout_end": b_end.isoformat(),
            "detections": []
        }
        
        # Find detections that fall strictly within this bout's timeframe
        if not dets_df.empty:
            mask = (dets_df["timestamp"] >= b_start) & (dets_df["timestamp"] <= b_end)
            bout_dets = dets_df[mask]
            
            for _, det in bout_dets.iterrows():
                bout_data["detections"].append({
                    "timestamp": det["timestamp"].isoformat(),
                    "description": det.get("description", ""),
                    "source": det.get("source", ""),
                    "category": det.get("category", "")
                })
                
        result.append(bout_data)
        
    return result

def format_bout_data_to_text(bout_list, display_tz="America/Los_Angeles"):
    if not bout_list:
        return "*No whale bouts found for this specific date.*"

    lines = []
    for i, bout in enumerate(bout_list, 1):
        b_start = pd.Timestamp(bout["bout_start"]).tz_convert(display_tz).strftime("%Y-%m-%d %H:%M %Z")
        b_end = pd.Timestamp(bout["bout_end"]).tz_convert(display_tz).strftime("%Y-%m-%d %H:%M %Z")
        dets = bout.get("detections", [])

        lines.append(f"**Bout {i}**: {b_start} to {b_end} *(Detections: {len(dets)})*")

        for d in dets:
            d_time = pd.Timestamp(d["timestamp"]).tz_convert(display_tz).strftime("%Y-%m-%d %H:%M:%S %Z")
            desc = d.get("description", "") or "No description"
            cat = d.get("category", "") or "Unknown"
            lines.append(f"&emsp; ↳ *{d_time}* — **{cat}**: {desc}")

        lines.append("")

    return "\n".join(lines)

print(fetch_bout_data(datetime(2026,2,7), datetime(2026,2,27)))