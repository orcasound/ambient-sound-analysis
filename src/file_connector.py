import datetime as dt
from enum import Enum

import boto3
from botocore import UNSIGNED
from botocore.config import Config

class Bucket(Enum):
    """
    Enum for orcasound AWS S3 Buckets
    """

    BUSH_POINT = "rpi_bush_point"
    ORCASOUND_LAB = "rpi_orcasound_lab"
    PORT_TOWNSEND = "rpi_port_townsend"
    SUNSET_BAY = "rpi_sunset_bay"
    SANDBOX = "acoustic-sandbox/noise-analysis"

class S3FileConnector:

    def __init__(self, bucket: Bucket):
        
        self.bucket = bucket
        self.client = boto3.client('s3', config=Config(signature_version=UNSIGNED))

    @staticmethod
    def create_filename(start: dt.datetime, end: dt.datetime, secs_per_sample: int, hz_bands:(int|str)):
        """ Create a filename with the given daterange and granularity. Dates must be in UTC """

        dt_format = "%Y%m%dT%H%M%S"

        start_str = start.strftime(dt_format)
        end_str = end.strftime(dt_format)
        sec_str = f"{secs_per_sample}s"
        freq_str = str(hz_bands) + ('hz' if isinstance(hz_bands, int) else '')

        return f"{start_str}_{end_str}_{sec_str}_{freq_str}.parquet"

    def save_file(self, file, start: dt.datetime, end: dt.datetime, secs_per_sample: int=60, hz_bands:(int|str)=100):
        """Writes a file object to S3. Name is calcualted from inputs. File will not be closed automatically, but will be spooled to end."""

        # Generate filename
        filename = self.create_filename(start, end, secs_per_sample, hz_bands)

        # Write file
        self.client.put_object(Body=file, Bucket=self.bucket, Key=f"{self.bucket}/{filename}")


    