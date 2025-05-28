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
from resources.grids.game_grid import GameGrid, EMPTY_SYMB

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
            width, height = grid1.get_dimensions()
            game_instance = self.add_game_instance(experiment, instance_id)
            game_instance['width'] = width
            game_instance['height'] = height
            game_instance['empty_symbol'] = EMPTY_SYMB
            game_instance['grid1'] = grid1.__str__(empty=True)
            game_instance['objects1'] = grid1.objects
            game_instance['grid2'] = grid2.__str__(empty=True)
            game_instance['objects2'] = grid2.objects
            game_instance['initial_prompt'] = self.load_template('resources/initial_prompts/initial_prompt')
            game_instance['p1_start'] = self.load_template('resources/initial_prompts/p1_start')
            game_instance['p2_start'] = self.load_template('resources/initial_prompts/p2_start')
            game_instance['new_turn'] = self.load_template('resources/new_turn_prompts/new_turn')
            game_instance['new_turn_move'] = self.load_template('resources/new_turn_prompts/new_turn_move')
            game_instance['move_pattern'] = r'move\((?P<obj>[A-Z]),(?P<x>\d+),(?P<y>\d+)\)'
            game_instance['message_pattern'] = r'say\((?P<message>.+)\)'


if __name__ == '__main__':
    CleanUpInstanceGenerator().generate()
