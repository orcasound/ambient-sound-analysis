# AWS Batch Readme

This Readme instructs users on where to find the documentation required to recreate the AWS environments used to process 
the raw .ts audio files into parquet files. This conversion uses functions located in the pipeline directory, 
file_connector.py, hydrophone.py and orca-hls-utils.

All relevant documentation can be found in the [docs subfolder](docs).

1. To create an EC2 instance used to process audio data view the [Configuring_EC2_for_File_Processing.md](docs/Configuring_EC2_for_File_Processing.md)
2. To recreate the AWS batch service see [Creating_the_Batch_Service](docs/Creating_the_Batch_Service.md)

