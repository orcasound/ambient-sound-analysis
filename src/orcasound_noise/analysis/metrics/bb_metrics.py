import datetime as dt
from collections.abc import Sequence
from typing import Literal

import polars as pl

from ...utils import Hydrophone
from ..partitioned_accessor import PartitionedAccessor

BANDS = ("bb", "comm_bb", "ship_bb")
INTERVALS = {"minute": "1m", "hour": "1h", "day": "1d"}
Interval = Literal["minute", "hour", "day"]


def get_broadband_metrics(
    start: dt.datetime,
    end: dt.datetime,
    hydrophones: Hydrophone | Sequence[Hydrophone],
    interval: Interval = "hour",
) -> pl.DataFrame:
    """
    Load broadband data from S3 (Hive-partitioned parquet) and aggregate
    it by `minute`, `hour`, or `day`.

    Valid hydrophone names: `bush_point`, `orcasound_lab`,
    `port_townsend`, `sunset_bay`, `andrews_bay`, `mast_center`,
    `point_robinson`, `north_sjc`, `sandbox`.

    Returned metrics for each of `bb`, `comm_bb`, and `ship_bb`:
    `median`, `q05`, `q25`, `q75`, `q95`, `min`, `max`.
    """
    hydrophones = [hydrophones] if isinstance(hydrophones, Hydrophone) else list(hydrophones)
    if not hydrophones:
        raise ValueError("At least one hydrophone must be provided.")
    if interval not in INTERVALS:
        raise ValueError(
            f"Unsupported interval '{interval}'. Choose from {sorted(INTERVALS)}."
        )

    frames = [
        frame
        for hydrophone in hydrophones
        if (frame := _load_one_hydrophone(start, end, hydrophone)) is not None
    ]
    if not frames:
        return pl.DataFrame(
            schema={
                "hydrophone": pl.Utf8,
                "bucket_start": pl.Datetime,
            }
        )

    broadband_df = pl.concat(frames, how="diagonal_relaxed").sort(["hydrophone", "ind"])

    return (
        broadband_df.lazy()
        .with_columns(pl.col("ind").dt.truncate(INTERVALS[interval]).alias("bucket_start"))
        .group_by(["hydrophone", "bucket_start"])
        .agg(
            [
                expr
                for band in BANDS
                for expr in [
                    pl.col(band).median().alias(f"{band}_median"),
                    pl.col(band).quantile(0.05).alias(f"{band}_q05"),
                    pl.col(band).quantile(0.25).alias(f"{band}_q25"),
                    pl.col(band).quantile(0.75).alias(f"{band}_q75"),
                    pl.col(band).quantile(0.95).alias(f"{band}_q95"),
                    pl.col(band).min().alias(f"{band}_min"),
                    pl.col(band).max().alias(f"{band}_max"),
                ]
            ]
        )
        .sort(["hydrophone", "bucket_start"])
        .collect()
    )


def _load_one_hydrophone(
    start: dt.datetime,
    end: dt.datetime,
    hydrophone: Hydrophone,
) -> pl.DataFrame | None:
    try:
        accessor = PartitionedAccessor(hydrophone, start_time=start, end_time=end)
        df = accessor.bb_df.select(["ind", *BANDS]).collect()
    except Exception:
        return None

    if df.is_empty():
        return None

    return df.with_columns(
        pl.lit(hydrophone.value.name).alias("hydrophone"),
    )
