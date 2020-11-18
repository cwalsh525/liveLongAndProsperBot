import json
import sys
import os

base_path = os.path.dirname(os.path.abspath(sys.argv[0]))

with open(base_path + "/config/default_config.json") as config_file:
    config = json.load(config_file)
