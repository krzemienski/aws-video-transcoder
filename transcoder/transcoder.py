#!/usr/bin/env python

"""
A script that transcodes movie files to a different format.

"""

from __future__ import print_function

import glob
import json
import os

import boto3

from botocore.client import ClientError

from .roles import BASIC_ROLE, QUEUE_POLICY, S3_POLICY

class TranscodeError(Exception):
    pass

class Transcoder(object):
    """
    This is the main transcoder class, which exposes a ``run`` method
    to put everything into motion. It watches for new files, uploads
    them to S3, converts them using Elastic Transcoder and downloads
    the output from S3 back to your computer.
    """

    def __init__(self, **config):
        super(Transcoder, self).__init__()

        # Local (filesystem) related.
        self.unconverted_directory = config['unconverted_dir']
        self.converted_directory = config['converted_dir']
        self.existing_files = set()
        self.file_pattern = config['file_pattern']

        # AWS related.
        self.in_bucket_name = config['in_bucket']
        self.out_bucket_name = config['out_bucket']
        self.role_name = config['role_name']
        self.topic_name = config['topic_name']
        self.queue_name = config['queue_name']
        self.pipeline_name = config['pipeline_name']
        self.region_name = config['region_name']
        self.role_arn = None
        self.topic_arn = None
        self.queue_arn = None
        self.pipeline_id = None

        self.in_bucket = None
        self.out_bucket = None
        self.role = None
        self.queue = None

        # How often should we look at the local FS for updates?
        self.poll_interval = int(config['poll_interval'])

        self.s3 = boto3.resource('s3')
        self.iam = boto3.resource('iam')
        self.sns = boto3.resource('sns', self.region_name)
        self.sqs = boto3.resource('sqs', self.region_name)
        self.transcoder = boto3.client('elastictranscoder', self.region_name)

    def ensure_local_setup(self):
        """
        Ensures that the local directory setup is sane by making sure
        that the directories exist and aren't the same.
        """
        if self.unconverted_directory == self.converted_directory:
            raise TranscodeError(
                "The unconverted & converted directories can not be the same."
            )

        if not os.path.exists(self.unconverted_directory):
            os.makedirs(self.unconverted_directory)

        if not os.path.exists(self.converted_directory):
            os.makedirs(self.converted_directory)

    def ensure_aws_setup(self):
        """
        Ensures that the AWS services, resources, and policies are set
        up so that they can all talk to one another and so that we
        can transcode media files.
        """
        if self.bucket_exists(self.in_bucket_name):
            self.in_bucket = self.s3.Bucket(self.in_bucket_name)
        else:
            self.in_bucket = self.s3.create_bucket(
                Bucket=self.in_bucket_name)

        if self.bucket_exists(self.out_bucket_name):
            self.out_bucket = self.s3.Bucket(self.out_bucket_name)
        else:
            self.out_bucket = self.s3.create_bucket(
                Bucket=self.out_bucket_name)

        if self.iam_role_exists():
            self.role = self.iam.Role(self.role_name)
        else:
            self.role = self.setup_iam_role()

        self.topic_arn = self.get_sns_topic()
        self.queue = self.get_sqs_queue()

        self.pipeline_id = self.get_pipeline()

    def collect_files(self):
        """
        Get a list of all relevant files (based on the file extension)
        in the local unconverted media file directory.
        """
        path = os.path.join(self.unconverted_directory, self.file_pattern)
        return glob.glob(path)

    def check_unconverted(self):
        """
        Get a list of files that are present in the unconverted directory
        but not present in the converted directory. These are the files
        that should be uploaded and transcoded.
        If no files are present then an empty set is returned.
        """
        current_files = set(self.collect_files())

        if not current_files:
            return set()

        # Check the new set against the old, returning only new files not found
        # in the old set.
        return current_files.difference(self.existing_files)

    def start_converting(self, files_found):
        """
        Upload and convert each file. Uploads are processed in series
        while transcoding happens in parallel.
        """
        for filepath in files_found:
            filename = self.upload_to_s3(filepath)
            self.start_transcode(filename)
            self.existing_files.add(filepath)

    def process_completed(self):
        """
        Check the queue and download any completed files from S3 to your
        hard drive.
        """
        to_fetch = self.check_queue()

        for s3_file in to_fetch:
            self.show_s3_link(s3_file)

    # The boto-specific methods.
    def bucket_exists(self, bucket_name):
        """
        Returns ``True`` if a bucket exists and you have access to
        call ``HeadBucket`` on it, otherwise ``False``.
        """
        try:
            self.s3.meta.client.head_bucket(Bucket=bucket_name)
            return True
        except ClientError:
            return False

    def iam_role_exists(self):
        """
        Returns ``True`` if an IAM role exists.
        """
        try:
            self.iam.meta.client.get_role(RoleName=self.role_name)
            return True
        except ClientError:
            return None

    def setup_iam_role(self):
        """
        Set up a new IAM role and set its policy to allow Elastic
        Transcoder access to S3 and SNS. Returns the role.
        """
        role = self.iam.create_role(
            RoleName=self.role_name,
            AssumeRolePolicyDocument=json.dumps(BASIC_ROLE))
        self.iam.RolePolicy(self.role_name, 'more-permissions').put(
            PolicyDocument=json.dumps(S3_POLICY))
        return role

    def get_sns_topic(self):
        """
        Get or create the SNS topic.
        """
        # Creating a topic is idempotent, so if it already exists
        # then we will just get the topic returned.
        return self.sns.create_topic(Name=self.topic_name).arn

    def get_sqs_queue(self):
        """
        Get or create the SQS queue. If it is created, then it is
        also subscribed to the SNS topic, and a policy is set to allow
        the SNS topic to send messages to the queue.
        """
        # Creating a queue is idempotent, so if it already exists
        # then we will just get the queue returned.
        queue = self.sqs.create_queue(QueueName=self.queue_name)
        self.queue_arn = queue.attributes['QueueArn']

        # Ensure that we are subscribed to the SNS topic
        subscribed = False
        topic = self.sns.Topic(self.topic_arn)
        for subscription in topic.subscriptions.all():
            if subscription.attributes['Endpoint'] == self.queue_arn:
                subscribed = True
                break

        if not subscribed:
            topic.subscribe(Protocol='sqs', Endpoint=self.queue_arn)

        # Set up a policy to allow SNS access to the queue
        if 'Policy' in queue.attributes:
            policy = json.loads(queue.attributes['Policy'])
        else:
            policy = {'Version': '2008-10-17'}

        if 'Statement' not in policy:
            statement = QUEUE_POLICY
            statement['Resource'] = self.queue_arn
            statement['Condition']['StringLike']['aws:SourceArn'] = self.topic_arn
            policy['Statement'] = [statement]

            queue.set_attributes(Attributes={
                'Policy': json.dumps(policy)
            })

        return queue

    def get_pipeline(self):
        """
        Get or create a pipeline. When creating, it is configured
        with the previously set up S3 buckets, SNS topic, and IAM
        role. Returns its ID.
        """
        paginator = self.transcoder.get_paginator('list_pipelines')
        for page in paginator.paginate():
            for pipeline in page['Pipelines']:
                if pipeline['Name'] == self.pipeline_name:
                    return pipeline['Id']

        response = self.transcoder.create_pipeline(
            Name=self.pipeline_name,
            InputBucket=self.in_bucket_name,
            OutputBucket=self.out_bucket_name,
            Role=self.role.arn,
            Notifications={
                'Progressing': '',
                'Completed': self.topic_arn,
                'Warning': '',
                'Error': ''
            })

        return response['Pipeline']['Id']

    def upload_to_s3(self, filepath):
        """
        Upload a file to the S3 input file bucket.
        """
        filename = os.path.basename(filepath)
        with open(filepath, 'rb') as data:
            self.in_bucket.Object(filename).put(Body=data)        
        print("Uploaded raw video {0}".format(filename))
        self.delete_completed_files(filename)
        return filename

    def start_transcode(self, filename):
        """
        Submit a job to transcode a file by its filename. The
        built-in web system preset is used for the single output.
        """
        self.transcoder.create_job(
            PipelineId=self.pipeline_id,
            Input={
                'Key': filename,
                'FrameRate': 'auto',
                'Resolution': 'auto',
                'AspectRatio': 'auto',
                'Interlaced': 'auto',
                'Container': 'auto'
            },
            #todo: make this configurable in json
            Outputs=[{
                'Key': '.'.join(filename.split('.')[:-1]) + '.mp4',
                'PresetId': '1351620000001-000010'
            },{
                'Key': '.'.join(filename.split('.')[:-1]) + '.webm',
                'PresetId': '1351620000001-100240'
            }]
        )
        print("Started transcoding {0}".format(filename))

    def check_queue(self):
        """
        Check the queue for completed files and set them to be
        downloaded.
        """
        queue = self.queue
        to_fetch = []

        for msg in queue.receive_messages(WaitTimeSeconds=self.poll_interval):
            body = json.loads(msg.body)
            if body['Subject'] == 'test':
                break

            message = body.get('Message', '{}')
            outputs = json.loads(message).get('outputs', [])

            if not len(outputs):
                print("Saw no output in {0}".format(body))
                continue

            key = outputs[0].get('key')

            if not key:
                print("Saw no key in outputs in {0}".format(body))
                continue

            to_fetch.append(key)
            print("Completed {0}".format(key))
            msg.delete()

        return to_fetch

    def download_from_s3(self, s3_file):
        """
        Download a file from the S3 output bucket to your hard drive.
        """
        destination_path = os.path.join(
            self.converted_directory,
            os.path.basename(s3_file)
        )
        body = self.out_bucket.Object(s3_file).get()['Body']
        with open(destination_path, 'wb') as dest:
            # Here we write the file in chunks to prevent
            # loading everything into memory at once.
            for chunk in iter(lambda: body.read(4096), b''):
                dest.write(chunk)

        print("Downloaded {0}".format(destination_path))

    # End boto-specific methods.

    def delete_completed_files(self, filepath):
        """Deletes files which are completed with the transcoding process"""
        os.remove(self.unconverted_directory + "/" + filepath)

    def show_s3_link(self, filename):
        """Print cloudfront link in console"""
        #todo: this should print a url for each file format
        print("URL to new video: https://s3-{region}.amazonaws.com/{out_bucket}/{filename}".format(
            region=self.region_name,
            out_bucket=self.out_bucket_name,
            filename=filename
        ))

    def run(self):
        """
        Start the main loop. This repeatedly checks for new files,
        uploads them and starts jobs if needed, and checks for and
        downloads completed files. It sleeps for ``poll_interval``
        seconds between checks.
        """
        # Make sure everything we need is setup, both locally & on AWS.
        self.ensure_local_setup()
        self.ensure_aws_setup()

        while True:
            try:
                # Run forever, or until the user says stop.
                print("Checking for new files.")
                files_found = self.check_unconverted()

                if files_found:
                    print("Found {0} new file(s).".format(len(files_found)))
                    self.start_converting(files_found)

                # Here we check the queue, which will long-poll
                # for up to ``self.poll_interval`` seconds.
                self.process_completed()

            except KeyboardInterrupt:
                print('\nStopping application.')
                break