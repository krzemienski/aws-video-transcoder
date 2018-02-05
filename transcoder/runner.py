#!/usr/bin/env python3.5

import os
import sys
import json

from .transcoder import Transcoder

class Configuration(object):
    """Create a configuration file which saves the information required
    for transcoding movies on aws"""
    
    empty_config_data = {
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

    def __init__(self):
        pass

    @classmethod
    def create_new_config(cls, config_filepath):
        """Skip if config exists, else create new json config"""
        if not os.path.exists(config_filepath):
            print("Created an empty config file at %s." % config_filepath)
            print("Please change the config and run this script again")
            with open(config_filepath, 'w') as config:
                json.dump(cls.empty_config_data, config, indent=4)
            sys.exit(1)

        print('config already exists: ~/.aws-transcode.json')

        
    @classmethod
    def load_from_config(cls, config_filepath):
        """Load a new transcoder from a JSON config file."""
        with open(config_filepath, 'r') as config:
            cfg = json.load(config)
            return Transcoder(**cfg)

def main():
    """Main entry of the script"""
    config_filepath = os.path.abspath(
        os.path.expanduser(
            '~/.aws-transcode.json'
        )
    )
    Configuration.create_new_config(config_filepath)
    auto = Configuration.load_from_config(config_filepath)
    auto.run()


if __name__ == '__main__':
    main()
