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

# Seed for reproducibility
random.seed(73128361)

N_INSTANCES = 10
LANGUAGE = 'en'

experiments = [
    {
        'name': 'gs11x11_obj5',
        'grid_file': 'resources/grids/gs11x11_b7.json',
        'objects': 'CHITW'
    },
    {
        'name': 'gs11x11_obj7',
        'grid_file': 'resources/grids/gs11x11_b7.json',
        'objects': 'POTSDAM'
    },
    {
        'name': 'gs11x11_obj9',
        'grid_file': 'resources/grids/gs11x11_b7.json',
        'objects': 'MAGISOULE'
    },
    {
        'name': 'gs11x16_obj7',
        'grid_file': 'resources/grids/gs11x16_b10.json',
        'objects': 'POTSDAM'
    },
    {
        'name': 'gs11x16_obj9',
        'grid_file': 'resources/grids/gs11x16_b10.json',
        'objects': 'MAGISOULE'
    },
    {
        'name': 'gs11x16_obj11',
        'grid_file': 'resources/grids/gs11x16_b10.json',
        'objects': 'ABCDEFGHIJK'
    },
    {
        'name': 'gs11x21_obj9',
        'grid_file': 'resources/grids/gs11x21_b15.json',
        'objects': 'MAGISOULE'
    },
    {
        'name': 'gs11x21_obj11',
        'grid_file': 'resources/grids/gs11x21_b15.json',
        'objects': 'ABCDEFGHIJK'
    },
    {
        'name': 'gs11x21_obj13',
        'grid_file': 'resources/grids/gs11x21_b15.json',
        'objects': 'ABCDEFGHIJKLM'
    }
]

class CleanUpInstanceGenerator(GameInstanceGenerator):
    def __init__(self):
        super().__init__(os.path.dirname(__file__))

    def on_generate(self):
        for experiment_conf in experiments:
            experiment = self.add_experiment(f"{experiment_conf['name']}_{LANGUAGE}")
            for instance_id in range(N_INSTANCES):
                grid1, grid2 = GameGrid.pair_from_json(experiment_conf['grid_file'])
                show_coords = True
                objects = experiment_conf['objects']
                max_penalties = len(objects) * 2
                max_rounds = len(objects) * 3
                background = grid1.__str__(empty=True, show_coords=False)
                grid1.place_objects(objects)
                grid2.place_objects(objects)
                width, height = grid1.get_dimensions()
                game_instance = self.add_game_instance(experiment, instance_id)
                game_instance['language'] = LANGUAGE
                game_instance['width'] = width
                game_instance['height'] = height
                game_instance['max_penalties'] = max_penalties
                game_instance['max_rounds'] = max_rounds
                game_instance['show_coords'] = show_coords
                game_instance['empty_symbol'] = EMPTY_SYMB
                game_instance['background'] = background
                game_instance['state1'] = grid1.object_list()
                game_instance['state2'] = grid2.object_list()
                grid1.show_coords = show_coords
                grid2.show_coords = show_coords
                game_instance['p1_initial_prompt'] = self.initial_prompt(grid1, max_penalties=10) + self.load_template('resources/initial_prompts/p1_start')
                game_instance['p2_initial_prompt'] = self.initial_prompt(grid2, max_penalties=10) + self.load_template('resources/initial_prompts/p2_start')
                game_instance['new_turn'] = self.load_template('resources/intermittent_prompts/new_turn')
                game_instance['new_turn_move'] = self.load_template('resources/intermittent_prompts/new_turn_move')
                game_instance['move_penalty'] = self.load_template('resources/intermittent_prompts/move_penalty')
                game_instance['penalty_counter'] = self.load_template('resources/intermittent_prompts/penalty_counter')
                game_instance['move_pattern'] = r'move\((?P<obj>[A-Z]),(?P<x>\d+),(?P<y>\d+)\)'
                game_instance['message_pattern'] = r'say\((?P<message>.+)\)'
                game_instance['terminate_question'] ='say(finished?)'
                game_instance['terminate_answer'] = 'say(finished!)'
                game_instance['restricted'] = ['[0-9]+', '\brows?', '\bcolumns?', '\bone\b', '\btwo\b', 
                                            '\bthree\b', '\bfour\b', '\bfive\b', '\bsix\b', '\bseven\b', 
                                            '\beight\b', '\bnine\b', '\bten\b', '\beleven\b', '\btwelve\b',
                                            '\bthirteen\b', '\bfirst\b', '\bsecond\b', '\bthird\b', '\bfourth\b',
                                            '\bfifth\b', '\bsixth\b', '\bseventh\b', '\beighth\b', '\bninth\b',
                                            '\btenth\b', '\beleventh\b', '\btwelfth\b', '\bthirteenth\b'
                                            ]
        # experiment = self.add_experiment(f"small_{LANGUAGE}")
        # for instance_id in range(N_INSTANCES):
        #     grid1, grid2 = GameGrid.pair_from_json('resources/grids/gs11x11_b7.json')
        #     show_coords = True
        #     objects = 'CHITW'
        #     max_penalties = len(objects) * 2    # Allow one penalty per object for each player
        #     max_rounds = len(objects) * 3   # Allow three turns per object
        #     background = grid1.__str__(empty=True, show_coords=False)
        #     grid1.place_objects(objects)
        #     grid2.place_objects(objects)
        #     width, height = grid1.get_dimensions()
        #     game_instance = self.add_game_instance(experiment, instance_id)
        #     game_instance['language'] = LANGUAGE
        #     game_instance['width'] = width
        #     game_instance['height'] = height
        #     game_instance['max_penalties'] = max_penalties
        #     game_instance['max_rounds'] = max_rounds
        #     game_instance['show_coords'] = show_coords
        #     game_instance['empty_symbol'] = EMPTY_SYMB
        #     game_instance['background'] = background
        #     game_instance['state1'] = grid1.object_list()
        #     game_instance['state2'] = grid2.object_list()
        #     grid1.show_coords = show_coords
        #     grid2.show_coords = show_coords
        #     game_instance['p1_initial_prompt'] = self.initial_prompt(grid1, max_penalties=10) + self.load_template('resources/initial_prompts/p1_start')
        #     game_instance['p2_initial_prompt'] = self.initial_prompt(grid2, max_penalties=10) + self.load_template('resources/initial_prompts/p2_start')
        #     game_instance['new_turn'] = self.load_template('resources/intermittent_prompts/new_turn')
        #     game_instance['new_turn_move'] = self.load_template('resources/intermittent_prompts/new_turn_move')
        #     game_instance['move_penalty'] = self.load_template('resources/intermittent_prompts/move_penalty')
        #     game_instance['penalty_counter'] = self.load_template('resources/intermittent_prompts/penalty_counter')
        #     game_instance['move_pattern'] = r'move\((?P<obj>[A-Z]),(?P<x>\d+),(?P<y>\d+)\)'
        #     game_instance['message_pattern'] = r'say\((?P<message>.+)\)'
        #     game_instance['terminate_question'] ='say(finished?)'
        #     game_instance['terminate_answer'] = 'say(finished!)'
        #     game_instance['restricted'] = ['[0-9]+', '\brows?', '\bcolumns?', '\bone\b', '\btwo\b', 
        #                                    '\bthree\b', '\bfour\b', '\bfive\b', '\bsix\b', '\bseven\b', 
        #                                    '\beight\b', '\bnine\b', '\bten\b', '\beleven\b', '\btwelve\b',
        #                                    '\bthirteen\b', '\bfirst\b', '\bsecond\b', '\bthird\b', '\bfourth\b',
        #                                    '\bfifth\b', '\bsixth\b', '\bseventh\b', '\beighth\b', '\bninth\b',
        #                                    '\btenth\b', '\beleventh\b', '\btwelfth\b', '\bthirteenth\b'
        #                                    ]
            # TODO: how to prohibit numbers in different languages?

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
            empty_symbol=EMPTY_SYMB,
            max_penalties=max_penalties
        )

if __name__ == '__main__':
    CleanUpInstanceGenerator().generate()