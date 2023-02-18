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
    SANDBOX = "acoustic-sandbox"

class S3FileConnector:

    DT_FORMAT = "%Y%m%dT%H%M%S"

    def __init__(self, bucket: Bucket):
        """
        S3File Connector maintains a connection to an AWS s3 bucket.
        """
        self.bucket = bucket
        self.client = boto3.client('s3', config=Config(signature_version=UNSIGNED))

    @classmethod
    def create_filename(cls, start: dt.datetime, end: dt.datetime, secs_per_sample: int, hz_bands):
        """ Create a filename with the given daterange and granularity. Dates must be in UTC """

        start_str = start.strftime(cls.DT_FORMAT)
        end_str = end.strftime(cls.DT_FORMAT)
        sec_str = f"{secs_per_sample}s"
        freq_str = str(hz_bands) + ('hz' if isinstance(hz_bands, int) else '')

        return f"{start_str}_{end_str}_{sec_str}_{freq_str}.parquet"

    @classmethod
    def parse_filename(cls, filename: str):
        """
        Helper function to extract data from filename.

        # Return
        startdt, enddt, secs_per_sample, hz_band list
        """

        args = filename.replace(".parquet", "").split("_")
        print(args)
        args[0] = dt.datetime.strptime(args[0], cls.DT_FORMAT)
        args[1] = dt.datetime.strptime(args[1], cls.DT_FORMAT)
        args[2] = int(args[2].replace("s", ""))
        args[3] = int(args[3].replace("hz", ""))
        try:
            args[3] = int(args[3])
        except ValueError:
            pass

        return args

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
        else:
            opened_file = False
        
        try:
            response = self.client.upload_fileobj(file, self.bucket.value, file_name)
        except ClientError as e:
            logging.error(e)
            return False
        else:
            return True
        finally:
            if opened_file:
                file.close()


    
