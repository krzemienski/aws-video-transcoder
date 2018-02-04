# The following policies are for the IAM role.
BASIC_ROLE = {
    'Statement': [
        {
            'Principal': {
                'Service': ['elastictranscoder.amazonaws.com']
            },
            'Effect': 'Allow',
            'Action': ['sts:AssumeRole']
        },
    ]
}

S3_POLICY = {
    'Statement': [
        {
            'Effect':'Allow',
            'Action': [
                's3:ListBucket',
                's3:Put*',
                's3:Get*',
                's3:*MultipartUpload*'
            ],
            'Resource': '*'
        },
        {
            'Effect': 'Allow',
            'Action': [
                'sns:*',
            ],
            'Resource': '*',
        },
        {
            'Effect': 'Allow',
            'Action': [
                'sqs:*',
            ],
            'Resource': '*',
        },
        {
            'Effect': 'Deny',
            'Action': [
                's3:*Policy*',
                'sns:*Permission*',
                'sns:*Delete*',
                'sqs:*Delete*',
                's3:*Delete*',
                'sns:*Remove*'
            ],
            'Resource':'*'
        },
    ]
}

# The SQS queue needs a policy to allow the SNS topic to post to it.
QUEUE_POLICY = {
    "Sid": "auto-transcode",
    "Effect": "Allow",
    "Principal": {
        "AWS": "*"
    },
    "Action": "SQS:SendMessage",
    "Resource": "<SQS QUEUE ARN>",
    "Condition": {
        "StringLike": {
            "aws:SourceArn": "<SNS TOPIC ARN>"
        }
    }
}