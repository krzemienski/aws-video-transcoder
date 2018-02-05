from setuptools import setup

setup(name='aws-video-transcoder',
      version='0.2',
      description='Transcodes videos to web-proof formats such as webp.',
      url='https://github.com/zwennesm/aws-video-transcoder',
      author='Martijn Zwennes',
      author_email='martijn.zwennes@debijenkorf.nl',
      license='MIT',
      packages=['transcoder'],
      scripts=['bin/aws-video-transcoder'],
      install_requires=[
          'boto3',
      ],
      zip_safe=False)