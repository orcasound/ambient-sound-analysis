import pandas as pd
import polars as pl
import datetime as dt
import geopandas as gpd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

s3_path = "s3://acoustic-sandbox/ambient-sound-analysis/data_2.0/psd/"

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
    
# print(fetch_acoustic_data(datetime(2026, 2, 7), datetime(2026, 2, 7, 0, 0, 0), datetime(2026, 2, 7, 23, 0, 0)))