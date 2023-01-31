import datetime as dt
import logging

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError

class FileConnector:
    
    def __init__(self, bucket: str):
        """
        File Connector maintains a connection to an AWS s3 bucket.
        """
    
        self.bucket = bucket
        self.s3_client = boto3.client('s3', config=Config(signature_version=UNSIGNED))

    def upload_file(self, file, hydrophone: str, as_of_date: dt.date):
        """
        Upload a parquet file to the S3 archive

        * file: File object to upload. Must be in bytemode
        * Hydrophone: Name of the hydrophone to uplaod to
        * as_of_date: The day the file represents

        # Return
        True if successfull upload, False otherwise
        """

        
        file_name = f"{hydrophone}/{as_of_date.year}/{as_of_date:%Y-%m-%d}.parquet"

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