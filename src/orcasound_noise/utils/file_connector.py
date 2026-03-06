import datetime as dt
import logging
import subprocess
from tracemalloc import start

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

from .hydrophone import Hydrophone

class S3FileConnector:

    DT_FORMAT = "%Y%m%dT%H%M%S"

    def __init__(self, hydrophone: Hydrophone, no_sign=False, env_file: str = None):
        """
        S3File Connector maintains a connection to an AWS s3 bucket.
        
        Args:
            hydrophone: Hydrophone enum value
            no_sign: If True, use unsigned requests. If False, use AWS credentials from environment
            env_file: Optional path to .env file for local development. If provided, environment 
                     variables will be loaded from this file. Not recommended for production.
        """
        # Load environment variables from file if provided (for local development)
        if env_file:
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file)
            except ImportError:
                logging.warning(f"dotenv not installed. Unable to load {env_file}. "
                                "Relying on OS environment variables.")
        self.bucket = hydrophone.value.bucket
        self.ref_folder = hydrophone.value.ref_folder
        self.save_bucket = hydrophone.value.save_bucket
        self.save_folder = hydrophone.value.save_folder

        if no_sign:
            self.client = boto3.client('s3', config=Config(signature_version=UNSIGNED), region_name='us-west-2')
            self.source_resource = boto3.resource('s3', config=Config(signature_version=UNSIGNED)).Bucket(self.bucket)
            self.archive_resource = boto3.resource('s3', config=Config(signature_version=UNSIGNED)).Bucket(self.save_bucket)
        else:
            # boto3 automatically looks for credentials in environment variables
            # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or AWS_SESSION_TOKEN
            self.client = boto3.client('s3')
            self.source_resource = boto3.resource('s3').Bucket(self.bucket)
            self.archive_resource = boto3.resource('s3').Bucket(self.save_bucket)


    @classmethod
    def create_filename(cls, start: dt.datetime, end: dt.datetime, secs_per_sample: int, delta_hz: int = None, octave_bands: int = None, is_broadband: bool =False):
        """ Create a filename with the given daterange and granularity. Dates must be in UTC """

        if is_broadband:
            freq_str = "broadband"
        elif octave_bands is not None:
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
        if args[3] == "broadband":
            args[3] = 0
            args.append("broadband")
        elif "hz" in args[3]:
            args[3] = int(args[3].replace("hz", ""))
            args.append("delta_hz")
        elif "oct" in args[3]:
            args[3] = int(args[3].replace("oct", ""))
            args.append("octave_bands")

        return args

    def upload_file(self, file, start: dt.datetime, end: dt.datetime, secs_per_sample: int, delta_hz: int = None, octave_bands: int = None, is_broadband: bool =False):
        """
        Upload a parquet file to the S3 archive

        * file: File object to upload. Must be in bytemode
        * Hydrophone: Name of the hydrophone to uplaod to
        * as_of_date: The day the file represents

        # Return
        True if successfull upload, False otherwise
        """

        
        file_name = self.create_filename(start, end, secs_per_sample, delta_hz=delta_hz, octave_bands=octave_bands, is_broadband=is_broadband)

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

    def upload_partitioned_folder(self, folder_path: str):
        """
        Upload a partitioned parquet folder to the S3 archive

        Uses AWS CLI to perform the upload to handle partitioned folders and upload only new files.
        Requires the `aws` CLI to be installed and available on PATH.

        * folder_path: Path to the local folder containing partitioned parquet files.
          The local folder path must include the S3 key prefix used by this connector
          (i.e. ``self.save_folder``) so that the local partition hierarchy matches
          the S3 key structure.
          For example, if:
            - ``self.save_bucket = "orcasound-noise"``
            - ``self.save_folder = "ambient-sound-analysis/data/"``
          then a valid ``folder_path`` could be::
              /local/path/ambient-sound-analysis/data/
            or::
              /local/path/ambient-sound-analysis/data/hydrophone=orcasound_lab/year=2023
          In general, ``folder_path`` should contain ``self.save_folder`` as a substring.
        """
        if self.save_folder not in folder_path:
            raise ValueError(f"folder_path must include '{self.save_folder}' to match S3 key prefix.")
        
        # Use AWS CLI to sync folder to S3
        try:
            subprocess.run(
                [
                    "aws", "s3", "sync",
                    folder_path, f"s3://{self.save_bucket}/{self.save_folder}/",
                    "--no-overwrite",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            logging.error(
                "AWS CLI is not installed or not found in PATH. "
                "Please install and configure the AWS CLI to use upload_partitioned_folder."
            )
            raise
        except subprocess.CalledProcessError as exc:
            logging.error(
                "AWS CLI sync command failed with return code %s.\nStdout:\n%s\nStderr:\n%s",
                exc.returncode,
                exc.stdout,
                exc.stderr,
            )
            raise

    def get_files(self, start: dt.datetime, end: dt.datetime, secs_per_sample: int, hz_bands=None, is_broadband=False):
        """
        Get files within datetime range and matching optional sec and hz band requirements.

        * start: datetime, start point of range to search
        * end: datetime, end point of range to search
        * secs_per_sample: Int, the requested time frequency
        * hz_bands: Str, the hz bands to find. Can be in '50hz' format for linear bands or '3oct' format for octal bands

        # Return
        List of filepaths that meet the search criteria

        """

        # Setup
        all_files = []

        if is_broadband:
            suffix = f"{secs_per_sample}s_broadband.parquet"
        else:
            suffix = f"{secs_per_sample}s_{hz_bands}.parquet"

        for my_bucket_object in self.archive_resource.objects.filter(Prefix=self.save_folder):
            filename = my_bucket_object.key.split("/")[-1]
            if not filename.endswith(suffix):
                continue

            fstart, fend, _, _, __ = self.parse_filename(filename)

            if fend >= start and fstart <= end:

                all_files.append(my_bucket_object.key)

        return all_files

    def download_file(self, filename, location):
            self.client.download_file(self.save_bucket, filename, location)

class ShipMetricsS3Connector:

    def __init__(self, no_sign=False, env_file: str = None):
        """
        S3File Connector maintains a connection to an AWS s3 bucket for ship metrics.
        
        Args:
            no_sign: If True, use unsigned requests. If False, use AWS credentials from environment
            env_file: Optional path to .env file for local development. If provided, environment 
                     variables will be loaded from this file. Not recommended for production.
        """

        # Load environment variables from file if provided (for local development)
        if env_file:
            try:
                from dotenv import load_dotenv
                load_dotenv(env_file)
            except ImportError:
                logging.warning(f"dotenv not installed. Unable to load {env_file}. "
                                "Relying on OS environment variables.")
                

        self.bucket = 'audio-orcasound-net'
        self.save_bucket = "acoustic-sandbox"
        # self.save_folder = "ambient-sound-analysis/temp_ship_metrics/"
        self.save_folder = "ambient-sound-analysis/ship_metrics/test"

        if no_sign:
            self.client = boto3.client('s3', config=Config(signature_version=UNSIGNED), region_name='us-west-2')
            self.source_resource = boto3.resource('s3', config=Config(signature_version=UNSIGNED)).Bucket(self.bucket)
            self.archive_resource = boto3.resource('s3', config=Config(signature_version=UNSIGNED)).Bucket(self.save_bucket)
        else:
            # boto3 automatically looks for credentials in environment variables
            # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or AWS_SESSION_TOKEN
            self.client = boto3.client('s3')
            self.source_resource = boto3.resource('s3').Bucket(self.bucket)
            self.archive_resource = boto3.resource('s3').Bucket(self.save_bucket)

        
    def upload_file(self, file, file_name) -> bool:
        """
        Upload a parquet file to the S3 archive
        
        Args:
            file: File object to upload. Must be in bytemode
            file_name: Name of the file to save in S3
        
        Return:
            Bool, True if successful upload, False otherwise
        """


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


    def upload_partitioned_folder(self, folder_path: str):
        """
        Upload a partitioned parquet folder to the S3 archive

        Uses AWS CLI to perform the upload to handle partitioned folders and upload only new files.
        Requires the `aws` CLI to be installed and available on PATH.

        Args:
            folder_path: Path to the local folder containing partitioned parquet files.
        """
        if self.save_folder not in folder_path:
            raise ValueError(f"folder_path must include '{self.save_folder}' to match S3 key prefix.")
        
        # Use AWS CLI to sync folder to S3
        try:
            subprocess.run(
                [
                    "aws", "s3", "sync",
                    folder_path, f"s3://{self.save_bucket}/{self.save_folder}/",
                    # "--no-overwrite", 
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            logging.error(
                "AWS CLI is not installed or not found in PATH. "
                "Please install and configure the AWS CLI to use upload_partitioned_folder."
            )
            raise
        except subprocess.CalledProcessError as exc:
            logging.error(
                "AWS CLI sync command failed with return code %s.\nStdout:\n%s\nStderr:\n%s",
                exc.returncode,
                exc.stdout,
                exc.stderr,
            )
            raise
    
    def download_file(self, filename, location):
        self.client.download_file(self.save_bucket, filename, location)
