import datetime as dt
import logging
from enum import Enum

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

     
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
        """
        S3File Connector maintains a connection to an AWS s3 bucket.
        """
        self.bucket = bucket
        self.client = boto3.client('s3', config=Config(signature_version=UNSIGNED))

    @staticmethod
    def create_filename(start: dt.datetime, end: dt.datetime, secs_per_sample: int, hz_bands):
        """ Create a filename with the given daterange and granularity. Dates must be in UTC """

        dt_format = "%Y%m%dT%H%M%S"

        start_str = start.strftime(dt_format)
        end_str = end.strftime(dt_format)
        sec_str = f"{secs_per_sample}s"
        freq_str = str(hz_bands) + ('hz' if isinstance(hz_bands, int) else '')

        return f"{start_str}_{end_str}_{sec_str}_{freq_str}.parquet"

    def upload_file(self, file, start: dt.datetime, end: dt.datetime, secs_per_sample: int, hz_bands):
        """
        Upload a parquet file to the S3 archive

        * file: File object to upload. Must be in bytemode
        * Hydrophone: Name of the hydrophone to uplaod to
        * as_of_date: The day the file represents

        # Return
        True if successfull upload, False otherwise
        """

        
        file_name = self.create_filename(start, end, secs_per_sample, hz_bands)

        # If file path, open as object
        if isinstance(file, str):
            file = open(file, 'rb')
            opened_file = True

        try:
            response = self.s3_client.upload_fileobj(file, self.bucket, file_name)
        except ClientError as e:
            logging.error(e)
            return False
        else:
            return True
        finally:
            if opened_file:
                file.close()


        bucket_list = [int(bucket) for bucket in bucket_list]
        start_index = 0
        end_index = len(bucket_list) - 1
        while int(bucket_list[start_index]) < int(start_time):
            start_index += 1
        while int(bucket_list[end_index]) > int(end_time):
            end_index -= 1
        return bucket_list[start_index-1:end_index + 1]


    
