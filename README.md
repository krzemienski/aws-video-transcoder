# AWS Video transcoder
This module converts videos to a web-friendly format such as mp4 and webm by using the Elastic Transcoder from the AWS platform. Using the module is fairly straight forward and can be used with the command-line. 

## Requirements 
* Python 3.x
* pip

## Getting started
Installing the module is as easy as running `pip install aws-video-transcoder`. The module will be installed on your local machine which makes it possible to transcode videos.

## Running the first time
A configuration file is created in `~/.aws-transcode.json` when running the `aws-video-transcoder` job for the first time. The following json is an example of the config file:

```
    {
        'unconverted_dir': "<PLEASE PROVIDE A LOCAL DIRECTORY FOR INPUT FILES>",
        'converted_dir': "<PLEASE PROVIDE A LOCAL DIRECTORY FOR OUTPUT FILES>",
        'in_bucket': "<PLEASE PROVIDE AN INPUT BUCKET NAME>",
        'out_bucket': "<PLEASE PROVIDE AN OUTPUT BUCKET NAME>",
        'role_name': 'autotranscode-user',
        'topic_name': 'autotranscode-complete',
        'queue_name': 'autotranscode',
        'pipeline_name': 'autotranscode-pipe',
        'poll_interval': 10,
        'region_name': 'eu-west-1',
        'file_pattern': '*.mp4'
    }
```

## Transcoding videos
Once the configuration file is created it's possible to start transcoding by running the `aws-video-transcoder` command again. The command will now make sure that all the required resources are created. 
The following resources will be created:
* IAM Role
* input & output S3 bucket
* SNS topic & subscription
* SQS queue
* Elastic Transcoder pipeline

Once the resource are created the application will start searching the input folder for files which can be sent to S3 for transcoding. Once the transcoding is completed the output will be written to the
output S3 bucket and the user will be informed via the SQS message queue.

## Authentication
Your local `aws-cli` settings are used (default profile) so make sure that the default account (you can change this with export AWS_PROFILE=<ACCOUNT>) has clearance to create the resources named above.

## Regarding presets
Currently the presets are hard-coded into the application. System defined presets are used in order to make the application usable for others as well. 
