import datetime as dt
import geopandas as gpd
import pandas as pd
import polars as pl
from shapely.geometry import Point
import time

from orcasound_noise.analysis.partitioned_accessor import PartitionedAccessor
from orcasound_noise.utils import Hydrophone
from orcasound_noise.pipeline.pipeline import ShipAnalysisPipeline


class ShipMetricsCalculator:
    def __init__(self, lf_radar: pl.LazyFrame, lf_ais: pl.LazyFrame, lf_bb: pl.LazyFrame):
        """
        Initializes the ShipMetricsCalculator with raw radar, AIS, and sound data.

        lf_radar: LazyFrame with raw radar track data from M2
        lf_ais: LazyFrame with raw AIS data from M2
        lf_bb: LazyFrame with broadband sound data
        """
        self.lf_radar = self.get_valid_radar_data(lf_radar)
        self.lf_ais = self.clean_ais_data(lf_ais)
        self.lf_sound = lf_bb 
        self.hydrophone_metadata = {'coordinates': [-123.1735774, 48.5583362], # Orcasound_lab coordinates
                                    'crs': {'properties': {'name': 'EPSG:4326'},  # CRS for lat/lon
                                            'type': 'name'}, 'type': 'Point'}
        
    
    def clean_ais_data(self, lf_ais: pl.LazyFrame) -> pl.LazyFrame:
        """
        Processes raw AIS data to create a valid Polars DataFrame
        with timestamps and cleaned MMSI/IMO fields.
        
        lf_ais: LazyFrame with raw AIS data
        """
        return (
            lf_ais
            .with_columns([
                # Clean id_track, MMSI and IMO fields (remove trailing .0 if present)
                pl.col("id_track").cast(pl.Utf8).str.replace(r"\.0$", "").alias("id_track"),
                pl.col("mmsi").cast(pl.Utf8).str.replace(r"\.0$", "").alias("mmsi"),

                # remove imo because all values are either 0. or null
                # pl.col("imo").cast(pl.Utf8).str.replace(r"\.0$", "").alias("imo"),

                # rename type to type_id
                pl.col("type").alias("type_id")
            ]).select(
                ['id_track', 'mmsi', 'name', 'draft', 'type_id']
            )
        )
    
    def get_valid_radar_data(self, lf_radar: pl.LazyFrame) -> pl.LazyFrame:
        """
        Processes raw radar data to create a valid Polars DataFrame
        with timestamps and a validity flag based on confidence
        and available association ID.

        lr_radar: LazyFrame with raw radar data
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
        ''' 
        Maps AIS type_id to human-readable ship type categories based on AIS standards from M2.

        '''
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
        '''
        Joins AIS metadata to the radar LazyFrame based on the association ID.

        lf_radar: LazyFrame with radar tracks, must contain 'assoc_id' column
        '''
        return (
            lf_radar
            .join(
                self.lf_ais,
                left_on="assoc_id",
                right_on="id_track",
                how="left"
            )
            .with_columns(
                self.ship_type_expr().alias("type")
            ).drop(['assoc_id'])
        )
        
    def add_isolation_flag(self, lf_radar: pl.LazyFrame) -> pl.LazyFrame:
        '''
        Adds an 'is_isolated' boolean column to the radar LazyFrame indicating whether each track is isolated (no overlapping tracks) or not.

        lf_radar: LazyFrame with radar tracks
        '''
        # Create a version of the data to check for 'others'
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

    def add_acoustic_metrics(self, lf_radar: pl.LazyFrame, lf_sound: pl.LazyFrame, ref_comm_bb: float=0.0, ref_bb: float=0.0) -> pl.LazyFrame:
        """
        Calculates all quantiles for all ships in one lazy operation.

        lf_radar: LazyFrame with radar tracks
        lf_sound: LazyFrame with sound data
        ref_comm: reference community background noise level for LSR calculation # 76.3
        ref_bb: reference broadband noise level for LSR calculation # 76.6
        """
        
        # Define a helper function to calculate LSR for a given column and reference level
        def lsr(col_name, ref):
            '''
            Calculates the LSR for a given column and reference level using the formula:
            LSR = 100 * (1 - 10^(-2 * (col - ref) / 15))
            '''
            return 100 * (1 - 10 ** (-2 * (pl.col(col_name) - ref) / 15))
        
        # 1. Join sound data to radar tracks based on the time window
        # Replace "__index_level_0__" with actual sound timestamp column name
        combined = lf_radar.join_where(
            lf_sound,
            pl.col("s_timestamp") <= pl.col("__index_level_0__"),
            pl.col("l_timestamp") >= pl.col("__index_level_0__")
        )

       
        # 2. Define the aggregations
        quantile_exprs = []
        for col in ["comm_bb", "bb", "ship_bb"]:
            quantile_exprs.extend([
                pl.col(col).mean().alias(f"{col}_avg"),
                pl.col(col).quantile(0.05).alias(f"{col}_q05"),
                pl.col(col).quantile(0.25).alias(f"{col}_q25"),
                pl.col(col).quantile(0.50).alias(f"{col}_q50"),
                pl.col(col).quantile(0.75).alias(f"{col}_q75"),
                pl.col(col).quantile(0.95).alias(f"{col}_q95"),
            ])
        
        # 3. Calculate LSR for bb and comm_bb
        quantile_exprs.extend([
            lsr("bb", ref_bb).quantile(0.50).alias("bb_lsr_q50"),
            lsr("bb", ref_bb).quantile(0.95).alias("bb_lsr_q95"),
            lsr("comm_bb", ref_comm_bb).quantile(0.50).alias("comm_bb_lsr_q50"),
            lsr("comm_bb", ref_comm_bb).quantile(0.95).alias("comm_bb_lsr_q95"),
        ])

        # 4. Group by the track ID to collapse the sound samples into metrics
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
        df: Polars DataFrame with a 'geometry' column containing WKT LineStrings
        hydrophone_metadata: dict with 'coordinates' (lon, lat) and 'crs' (CRS info) for the hydrophone location
        target_crs: CRS to project geometries to for accurate distance calculation (default is UTM zone 10N for PNW, EPSG:32610)
        """

        from shapely.geometry import Point
        from shapely import wkt
        
        # Hydrophone point (lon, lat)
        lon, lat = hydrophone_metadata["coordinates"]
        crs = hydrophone_metadata["crs"]["properties"]["name"]
        hydro_pt = gpd.GeoSeries([Point(lon, lat)], crs=crs)

        # Convert Polars to pandas
        pdf = df.to_pandas()

        # Restore geometry stored as WKB
        pdf["geometry"] = pdf["geometry"].apply(wkt.loads)

        gdf = gpd.GeoDataFrame(pdf, geometry="geometry", crs=crs)

        # Project to metric CRS
        gdf_proj = gdf.to_crs(target_crs)
        hydro_proj = hydro_pt.to_crs(target_crs).iloc[0]

        distances = gdf_proj.distance(hydro_proj)

        return pl.Series("distance_m", distances.values)

    def get_all_ship_metrics(self) -> pl.DataFrame:
        '''
        Main function to calculate all ship metrics by combining radar, AIS, and sound data.
        '''
        # 1. Start with valid radar data
        lf_output = self.lf_radar.select([
            'id_track', 'assoc_id', 's_timestamp', 'l_timestamp', 'duration',
            'avg_speed', 'max_speed', 'min_speed',
            'distance', 'curviness', 'confidence', 'geometry'
        ])

        # 2. Get AIS Metadata via Join
        lf_output = self.join_ais_metadata(lf_output)
        
        # 3. Calculate Isolation
        lf_output = self.add_isolation_flag(lf_output)
        
        # 4. Acoustic Metrics
        lf_output = self.add_acoustic_metrics(lf_output, self.lf_sound)
        
        # 5. Distance to Hydrophone 
        # using collect and compute due to geopandas
        df_collected = lf_output.collect()
        dist_series = self.get_distance_to_hydrophone(df_collected, self.hydrophone_metadata)
        df_collected = df_collected.with_columns(min_dist = dist_series)
        df_collected = df_collected.drop("geometry")

        return df_collected
    

# Generate metrics and save to parquet

# if __name__ == "__main__":

#     ship_pipeline = ShipAnalysisPipeline()
#     print("DataFrames loaded")
#     s_time = time.time()

#     # For regular weekly data
#     # lf_ais, lf_radar = ship_pipeline.get_raw_data_from_m2()

#     # For 7 days
#     # lf_ais = gpd.read_file('data/temp/2026-02-20_weekly/tracks_ais_7Day.shp')
#     # lf_radar = gpd.read_file('data/temp/2026-02-20_weekly/tracks_radar_7Day.shp')  

#     # For testing with all data in Feb
#     lf_ais = gpd.read_file('data/ship/M2/26_2026_02/26_2026_02_tracks_ais.shp')
#     lf_radar = gpd.read_file('data/ship/M2/26_2026_02/26_2026_02_tracks_radar.shp')  
#     lf_ais["geometry"] = lf_ais.geometry.to_wkt()
#     lf_radar["geometry"] = lf_radar.geometry.to_wkt()
#     lf_ais = pl.from_pandas(lf_ais).lazy()
#     lf_radar = pl.from_pandas(lf_radar).lazy()
#     e_time = time.time()

#     print(f"Raw data loaded from M2 in {e_time - s_time:.2f} seconds")
    
#     print("Sound DataFrames loaded")
#     s_time = time.time()
    
#     # For regular weekly data
#     # start, end = ship_pipeline.s_date, ship_pipeline.e_date
#     # start = dt.datetime.combine(start, dt.time.min)
#     # end = dt.datetime.combine(end, dt.time.max)
#     # ac_orcalab = PartitionedAccessor(Hydrophone.ORCASOUND_LAB, start, end)

#     # lf_psd, lf_bb = ac_orcalab.get_dataframes(lazy=True)

#     # For testing with all data in Feb
#     lf_bb = pl.read_parquet('data/sound/broadband/hydrophone=orcasound_lab/year=2026/month=02').lazy()
#     e_time = time.time()
#     print(f"DataFrames collected in {e_time - s_time:.2f} seconds")

#     # sample data for testing
#     lf_bb = lf_bb.with_columns(
#         bb = pl.col("0"),
#         comm_bb = pl.lit(1) * pl.col("0"),
#         ship_bb = pl.lit(1) * pl.col("0")
#     )

#     print("calculate metrics")
#     s_time = time.time()
#     ship_metrics_cal = ShipMetricsCalculator(lf_radar, lf_ais, lf_bb)
#     pl_ship_metrics = ship_metrics_cal.get_all_ship_metrics()
#     e_time = time.time()
#     print(f"Ship metrics calculated in {e_time - s_time:.2f} seconds")
#     # print(pl_ship_metrics.head())

#     pl_ship_metrics = pl_ship_metrics.with_columns([
#         pl.col("s_timestamp").dt.year().alias("year"),
#         pl.col("s_timestamp").dt.to_string("%m").alias("month"),
#         pl.col("s_timestamp").dt.to_string("%d").alias("day")
#     ])

#     # saving metrics to parquet with partitioning by year/month/day
#     pl_ship_metrics.write_parquet(
#         "data/temp_ship",
#         use_pyarrow=True,
#         pyarrow_options={"partition_cols": ["year", "month", "day"]}
#     )  
    
   