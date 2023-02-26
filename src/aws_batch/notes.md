# Notes on AWS Batch

when building docker Images on a Mac M1, you must specify the platform with "--platform=linux/amd64" or the docker image
will fail when deployed to Fargate.