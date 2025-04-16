"""Template script for instance generation.

usage:
python3 instancegenerator.py
Creates instance.json file in ./in

"""
import json
import os
import random
import logging
import openai
import requests
import spacy
import argparse

from clemcore.clemgame import GameInstanceGenerator

logger = logging.getLogger(__name__)


N_INSTANCES = 20
# Seed for reproducibility
random.seed(73128361)

class SomeGameInstanceGenerator(GameInstanceGenerator):
    def __init__(self):
        super().__init__(os.path.dirname(__file__))

    def on_generate(self):
        pass


if __name__ == '__main__':
    SomeGameInstanceGenerator().generate()
