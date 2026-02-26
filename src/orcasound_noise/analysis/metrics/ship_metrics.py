import datetime as dt
import geopandas as gpd
import numpy as np
import pandas as pd
import polars as pl
from shapely.geometry import Point
import time

from orcasound_noise.analysis.partitioned_accessor import PartitionedAccessor
from orcasound_noise.utils import Hydrophone
from orcasound_noise.pipeline.pipeline import ShipAnalysisPipeline


class ShipMetricsCalculator:
    def __init__(self, lf_radar: pl.LazyFrame, lf_ais: pl.LazyFrame, lf_bb: pl.LazyFrame):
        self.pl_radar = self.get_valid_radar_data(lf_radar)
        self.pl_ais = self.clean_ais_data(lf_ais)
        self.pl_sound = lf_bb 
        self.hydrophone_metadata = {'coordinates': [-123.1735774, 48.5583362], # Orcasound_lab coordinates
                                    'crs': {'properties': {'name': 'EPSG:4326'}, 
                                            'type': 'name'}, 'type': 'Point'}
        
    
    def clean_ais_data(self, lf_ais: pl.LazyFrame) -> pl.LazyFrame:
        """
        Processes raw AIS data to create a valid Polars DataFrame
        with timestamps and cleaned MMSI/IMO fields.
        """
        return (
            lf_ais
            .with_columns([
                # Clean id_track, MMSI and IMO fields (remove trailing .0 if present)
                pl.col("id_track").cast(pl.Utf8).str.replace(r"\.0$", "").alias("id_track"),
                pl.col("mmsi").cast(pl.Utf8).str.replace(r"\.0$", "").alias("mmsi"),
                pl.col("imo").cast(pl.Utf8).str.replace(r"\.0$", "").alias("imo"),

                # rename type to type_id
                pl.col("type").alias("type_id")
            ]).select(
                ['id_track', 'mmsi', 'imo', 'name', 'draft', 'type_id']
            )
        )
    
    def get_valid_radar_data(self, lf_radar: pl.LazyFrame) -> pl.LazyFrame:
        """
        Processes raw radar data to create a valid Polars DataFrame
        with timestamps and a validity flag based on confidence
        and available association ID.
        """
        return (
            lf_radar
            .with_columns([
                # Create timestamps
                (pl.col("sdate") + " " + pl.col("stime"))
                    .str.strptime(pl.Datetime, strict=False)
                    .alias("s_timestamp"),

                (pl.col("ldate") + " " + pl.col("ltime"))
                    .str.strptime(pl.Datetime, strict=False)
                    .alias("l_timestamp"),

                (pl.col("assoc_id").cast(pl.Utf8).str.replace(r"\.0$", ""))
                .alias("assoc_id"),

                (pl.col("id_track").cast(pl.Utf8).str.replace(r"\.0$", ""))
                .alias("id_track"),

                # Validity flag
                (
                    (pl.col("confidence") >= 0.5) |
                    (pl.col("assoc_id").is_not_null())
                ).alias("valid")
            ])
            # Filter valid rows + non-null geometry
            .filter(
                (pl.col("valid")) &
                (pl.col("geometry").is_not_null())
            )
            .sort("s_timestamp")
        )

    def ship_type_expr(self):
        return (
            pl.when(pl.col("type_id").is_null())
            .then(None)
            .when(pl.col("type_id") <= 0)
            .then(pl.lit("-"))
            .when(pl.col("type_id") <= 19)
            .then(pl.lit("reserved"))
            .when(pl.col("type_id") <= 29)
            .then(pl.lit("wing_in_ground"))
            .when(pl.col("type_id") <= 30)
            .then(pl.lit("fishing"))
            .when(pl.col("type_id") <= 32)
            .then(pl.lit("towing"))
            .when(pl.col("type_id") == 33)
            .then(pl.lit("dredging_or_underwater_operations"))
            .when(pl.col("type_id") == 34)
            .then(pl.lit("diving_operations"))
            .when(pl.col("type_id") == 35)
            .then(pl.lit("military_operations"))
            .when(pl.col("type_id") == 36)
            .then(pl.lit("sailing"))
            .when(pl.col("type_id") == 37)
            .then(pl.lit("pleasure_craft"))
            .when(pl.col("type_id") <= 39)
            .then(pl.lit("reserved"))
            .when(pl.col("type_id") <= 49)
            .then(pl.lit("high_speed_craft"))
            .when(pl.col("type_id") == 50)
            .then(pl.lit("pilot_vessel"))
            .when(pl.col("type_id") == 51)
            .then(pl.lit("search_and_rescue_vessel"))
            .when(pl.col("type_id") == 52)
            .then(pl.lit("tug"))
            .when(pl.col("type_id") == 53)
            .then(pl.lit("port_tender"))
            .when(pl.col("type_id") == 54)
            .then(pl.lit("anti_pollution_equipment"))
            .when(pl.col("type_id") == 55)
            .then(pl.lit("law_enforcement"))
            .when(pl.col("type_id") <= 57)
            .then(pl.lit("spare_local_vessel"))
            .when(pl.col("type_id") == 58)
            .then(pl.lit("medical_transport"))
            .when(pl.col("type_id") == 59)
            .then(pl.lit("noncombatant_ship"))
            .when(pl.col("type_id") <= 69)
            .then(pl.lit("passenger"))
            .when(pl.col("type_id") <= 79)
            .then(pl.lit("cargo"))
            .when(pl.col("type_id") <= 89)
            .then(pl.lit("tanker"))
            .when(pl.col("type_id") <= 99)
            .then(pl.lit("other_type"))
            .otherwise(pl.lit("unknown"))
        )
            

    def join_ais_metadata(self, lf_radar: pl.LazyFrame) -> pl.LazyFrame:
        return (
            lf_radar
            .join(
                self.pl_ais,
                left_on="assoc_id",
                right_on="id_track",
                how="left"
            )
            .with_columns(
                self.ship_type_expr().alias("type")
            )
        )
        
    def add_isolation_flag(self, lf_radar: pl.LazyFrame) -> pl.LazyFrame:
        '''
        Adds an 'is_isolated' boolean column to the radar LazyFrame indicating whether each track is isolated (no overlapping tracks) or not.
        '''
        # 1. Create a version of the data to check for 'others'
        others = lf_radar.select(["id_track", "s_timestamp", "l_timestamp"])

        # Use join(how="cross") instead of "left" with on=None
        overlaps = (
            lf_radar.join(others, how="cross", suffix="_other")
            .filter(
                (pl.col("s_timestamp") <= pl.col("l_timestamp_other")) &
                (pl.col("l_timestamp") >= pl.col("s_timestamp_other")) &
                (pl.col("id_track") != pl.col("id_track_other"))
            )
            .select("id_track")
            .unique()
            .with_columns(is_isolated=pl.lit(False))
        )

        return (
            lf_radar.join(overlaps, on="id_track", how="left")
            .with_columns(
                pl.col("is_isolated").fill_null(True)
            )
        )

    def add_acoustic_metrics(self, lf_radar: pl.LazyFrame, lf_sound: pl.LazyFrame) -> pl.LazyFrame:
        """
        Calculates all quantiles for all ships in one lazy operation.
        """
        
        # 1. Join sound data to radar tracks based on the time window
        # Note: Using 'join_where' is the modern, fast way to do range joins in Polars
        # Replace "__index_level_0__" with your actual sound timestamp column name
        combined = lf_radar.join_where(
            lf_sound,
            pl.col("s_timestamp") <= pl.col("__index_level_0__"),
            pl.col("l_timestamp") >= pl.col("__index_level_0__")
        )

        # 2. Define the aggregations (these replace your get_quantiles logic)
        # We do this for all three columns (comm_bb, bb, ship_bb) at once
        quantile_exprs = []
        for col, prefix in [("comm_bb", "comm_bb"), ("bb", "bb"), ("ship_bb", "ship_bb")]:
            quantile_exprs.extend([
                pl.col(col).mean().alias(f"{prefix}_avg"),
                pl.col(col).quantile(0.05).alias(f"{prefix}_q05"),
                pl.col(col).quantile(0.25).alias(f"{prefix}_q25"),
                pl.col(col).quantile(0.50).alias(f"{prefix}_q50"),
                pl.col(col).quantile(0.75).alias(f"{prefix}_q75"),
                pl.col(col).quantile(0.95).alias(f"{prefix}_q95"),
            ])

        # 3. Group by the track ID to collapse the sound samples into metrics
        acoustic_stats = (
            combined
            .group_by("id_track")
            .agg(quantile_exprs)
        )

        # 4. Join back to the original tracks (to keep ships that had no sound data)
        return lf_radar.join(acoustic_stats, on="id_track", how="left")
  

    def get_distance_to_hydrophone(self, df: pl.DataFrame, hydrophone_metadata,
                               target_crs="EPSG:32610") -> pl.Series:
        
        """
        Compute minimum distance between each LineString track
        and the hydrophone point.
        Returns distance in meters.
        """
        from shapely.geometry import Point
        from shapely import wkt
        
        # Hydrophone point (lon, lat)
        lon, lat = hydrophone_metadata["coordinates"]
        hydro_pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326")

        # Convert Polars → pandas
        pdf = df.to_pandas()

        # If geometry stored as WKB
        pdf["geometry"] = pdf["geometry"].apply(wkt.loads)

        gdf = gpd.GeoDataFrame(pdf, geometry="geometry", crs="EPSG:4326")

        # Project to metric CRS
        gdf_proj = gdf.to_crs(target_crs)
        hydro_proj = hydro_pt.to_crs(target_crs).iloc[0]

        distances = gdf_proj.distance(hydro_proj)

        return pl.Series("distance_m", distances.values)

    def get_all_ship_metrics(self) -> pl.DataFrame:
        # 1. Start with valid radar data
        lf_output = self.pl_radar.select([
            'id_track', 'assoc_id', 's_timestamp', 'l_timestamp', 'duration',
            'avg_speed', 'max_speed', 'min_speed',
            'distance', 'curviness', 'confidence', 'geometry'
        ])

        # 2. Get AIS Metadata via Join (Vectorized)
        # Note: I updated get_ais_metadata logic to handle the join internally
        lf_output = self.join_ais_metadata(lf_output)
        
        # 3. Calculate Isolation (Vectorized)
        # We use a join-filter strategy instead of a row-wise loop
        lf_output = self.add_isolation_flag(lf_output)
        
        # 4. Acoustic Metrics
        lf_output = self.add_acoustic_metrics(lf_output, self.pl_sound)
        
        # 5. Distance to Hydrophone 
        # Since this uses GeoPandas, we must collect, compute
        df_collected = lf_output.collect()
        dist_series = self.get_distance_to_hydrophone(df_collected, self.hydrophone_metadata)
        df_collected = df_collected.with_columns(min_dist = dist_series)
        df_collected = df_collected.drop("geometry")

        return df_collected
    
    
if __name__ == "__main__":

    ship_pipeline = ShipAnalysisPipeline()
    print("DataFrames loaded")
    s_time = time.time()
    lf_ais, lf_radar = ship_pipeline.get_raw_data_from_m2()
    # lf_ais = gpd.read_file('data/temp/2026-02-20_weekly/tracks_ais_7Day.shp')
    # lf_radar = gpd.read_file('data/temp/2026-02-20_weekly/tracks_radar_7Day.shp')    
    # lf_ais["geometry"] = lf_ais.geometry.to_wkt()
    # lf_radar["geometry"] = lf_radar.geometry.to_wkt()
    # lf_ais = pl.from_pandas(lf_ais).lazy()
    # lf_radar = pl.from_pandas(lf_radar).lazy()
    e_time = time.time()
    print(f"Raw data loaded from M2 in {e_time - s_time:.2f} seconds")
    start, end = ship_pipeline.s_date, ship_pipeline.e_date
    start = dt.datetime.combine(start, dt.time.min)
    end = dt.datetime.combine(end, dt.time.max)
    ac_orcalab = PartitionedAccessor(Hydrophone.ORCASOUND_LAB, start, end)
    
    print("Sound DataFrames loaded")
    s_time = time.time()
    lf_psd, lf_bb = ac_orcalab.get_dataframes(lazy=True)
    e_time = time.time()
    print(f"DataFrames collected in {e_time - s_time:.2f} seconds")

    # sample data for testing
    lf_bb = lf_bb.with_columns(
        bb = pl.col("0"),
        comm_bb = pl.lit(1) * pl.col("0"),
        ship_bb = pl.lit(1) * pl.col("0")
    )

    print("calculate metrics")
    s_time = time.time()
    ship_metrics_cal = ShipMetricsCalculator(lf_radar, lf_ais, lf_bb)
    pl_radar = ship_metrics_cal.get_all_ship_metrics()
    e_time = time.time()
    print(f"Ship metrics calculated in {e_time - s_time:.2f} seconds")
    print(pl_radar.head())
   