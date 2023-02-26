import datetime as dt
import logging

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from .hydrophone import Hydrophone

class S3FileConnector:

    DT_FORMAT = "%Y%m%dT%H%M%S"

    def __init__(self, hydrophone: Hydrophone):
        """
        S3File Connector maintains a connection to an AWS s3 bucket.
        """
        self.bucket = hydrophone.value.bucket
        self.ref_folder = hydrophone.value.ref_folder
        self.save_bucket = hydrophone.value.save_bucket
        self.save_folder = hydrophone.value.save_folder

        load_dotenv('.aws-config')
        self.client = boto3.client('s3')
        self.resource = boto3.resource('s3').Bucket(self.bucket)

    @classmethod
    def create_filename(cls, start: dt.datetime, end: dt.datetime, secs_per_sample: int, delta_hz: int = None, octave_bands: int = None):
        """ Create a filename with the given daterange and granularity. Dates must be in UTC """

        if octave_bands is not None:
            freq_str = str(octave_bands) + "oct"
        elif delta_hz is not None:
            freq_str = str(delta_hz) + "hz"
        else:
            raise ValueError("One of delta_hz or octave_bands must be provided.")
        

        start_str = start.strftime(cls.DT_FORMAT)
        end_str = end.strftime(cls.DT_FORMAT)
        sec_str = f"{secs_per_sample}s"

        return f"{start_str}_{end_str}_{sec_str}_{freq_str}.parquet"

    @classmethod
    def parse_filename(cls, filename: str):
        """
        Helper function to extract data from filename.

        # Return
        startdt, enddt, secs_per_sample, freq_value, freq_type list
        """

        args = filename.replace(".parquet", "").split("_")

        args[0] = dt.datetime.strptime(args[0], cls.DT_FORMAT)
        args[1] = dt.datetime.strptime(args[1], cls.DT_FORMAT)
        args[2] = int(args[2].replace("s", ""))
        
        # Parse frequency
        if "hz" in args[3]:
            args[3] = int(args[3].replace("hz", ""))
            args.append("delta_hz")
        elif "oct" in args[3]:
            args[3] = int(args[3].replace("oct", ""))
            args.append("octave_bands")

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
            response = self.client.upload_fileobj(file, self.save_bucket, self.save_folder + "/" + file_name)
        except ClientError as e:
            logging.error(e)
            return False
        else:
            return True
        finally:
            if opened_file:
                file.close()

    def get_files(self, start: dt.datetime, end: dt.datetime, secs_per_sample: int, hz_bands):
        """
        Get files within datetime range and matching optional sec and hz band requirements

        """

        all_files = []

        for my_bucket_object in self.resource.objects.filter(Prefix=self.ref_folder):
            filename = my_bucket_object.key.split("/")[-1]
            fstart, fend, fsec, fhz = self.parse_filename(filename)
            if fstart >= start and fstart <= fend:
                all_files.append(my_bucket_object)

        return all_files
        
