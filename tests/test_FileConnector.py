import datetime as dt

from src.file_connector import S3FileConnector

def test_filename():
    filename = S3FileConnector.create_filename(
        dt.datetime(2023, 1, 1, 6, 30),
        dt.datetime(2023, 1, 1, 12, 30),
        60,
        100
    )

    assert filename == "20230101T063000_20230101T123000_60s_100hz.parquet"