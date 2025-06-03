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

from string import Template

from clemcore.clemgame import GameInstanceGenerator
from resources.grids.game_grid import GameGrid, EMPTY_SYMB

logger = logging.getLogger(__name__)

N_INSTANCES = 3
LANGUAGE = 'en'

# Seed for reproducibility
random.seed(73128361)

class CleanUpInstanceGenerator(GameInstanceGenerator):
    def __init__(self):
        super().__init__(os.path.dirname(__file__))

    def on_generate(self):
        experiment = self.add_experiment(f"small_{LANGUAGE}")
        for instance_id in range(N_INSTANCES):
            grid1, grid2 = GameGrid.pair_from_json('resources/grids/gs11x11_b7.json')
            grid1.place_objects('CLP')
            grid2.place_objects('CLP')
            width, height = grid1.get_dimensions()
            game_instance = self.add_game_instance(experiment, instance_id)
            game_instance['language'] = LANGUAGE
            game_instance['width'] = width
            game_instance['height'] = height
            game_instance['show_coords'] = True
            game_instance['empty_symbol'] = EMPTY_SYMB
            game_instance['grid1'] = grid1.__str__(empty=True, show_coords=False)
            game_instance['state1'] = grid1.object_list()
            game_instance['grid2'] = grid2.__str__(empty=True, show_coords=False)
            game_instance['state2'] = grid2.object_list()
            grid1.show_coords = True
            grid2.show_coords = True
            game_instance['p1_initial_prompt'] = self.initial_prompt(grid1, max_penalties=10) + self.load_template('resources/initial_prompts/p1_start')
            game_instance['p2_initial_prompt'] = self.initial_prompt(grid2, max_penalties=10) + self.load_template('resources/initial_prompts/p2_start')
            # game_instance['initial_prompt'] = self.load_template('resources/initial_prompts/initial_prompt_lenient')
            # game_instance['p2_start'] = self.load_template('resources/initial_prompts/p2_start')
            game_instance['new_turn'] = self.load_template('resources/intermittent_prompts/new_turn')
            game_instance['new_turn_move'] = self.load_template('resources/intermittent_prompts/new_turn_move')
            game_instance['move_penalty'] = self.load_template('resources/intermittent_prompts/move_penalty')
            game_instance['penalty_counter'] = self.load_template('resources/intermittent_prompts/penalty_counter')
            game_instance['move_pattern'] = r'move\((?P<obj>[A-Z]),(?P<x>\d+),(?P<y>\d+)\)'
            game_instance['message_pattern'] = r'say\((?P<message>.+)\)'
            game_instance['terminate_question'] ='say(finished?)'
            game_instance['terminate_answer'] = 'say(finished!)'
            game_instance['max_penalties'] = 10
            game_instance['max_rounds'] = 20

    def initial_prompt(self, grid: GameGrid, max_penalties: int = 10) -> str:
        """
        Returns the initial prompt for the game.
        :param grid: The game grid
        :return: The initial prompt string
        """
        initial_prompt = Template(self.load_template('resources/initial_prompts/initial_prompt_lenient'))
        return initial_prompt.substitute(
            grid=str(grid),
            objects=grid.object_string(),
            max_x=grid.width - 1,
            max_y=grid.height - 1,
            empty_symbol=EMPTY_SYMB,
            max_penalties=max_penalties
        )

if __name__ == '__main__':
    CleanUpInstanceGenerator().generate()
