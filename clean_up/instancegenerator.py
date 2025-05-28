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
from resources.grids.game_grid import GameGrid

logger = logging.getLogger(__name__)

N_INSTANCES = 5
LANGUAGE = 'en'

# Seed for reproducibility
random.seed(73128361)

class CleanUpInstanceGenerator(GameInstanceGenerator):
    def __init__(self):
        super().__init__(os.path.dirname(__file__))

    def on_generate(self):
        experiment = self.add_experiment(f"small_{LANGUAGE}")
        for instance_id in range(N_INSTANCES):
            grid1, grid2 = GameGrid.pair_from_json()
            grid1.place_objects('CLP')
            grid2.place_objects('CLP')
            game_instance = self.add_game_instance(experiment, instance_id)
            game_instance['grid1'] = grid1.__str__(empty=True)
            game_instance['objects1'] = grid1.objects
            game_instance['grid2'] = grid2.__str__(empty=True)
            game_instance['objects2'] = grid2.objects

if __name__ == '__main__':
    CleanUpInstanceGenerator().generate()
