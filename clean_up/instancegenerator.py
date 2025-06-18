"""Template script for instance generation.

usage:
python3 instancegenerator.py
Creates instance.json file in ./in

"""
import json
import os
import random
import logging

from string import Template

from clemcore.clemgame import GameInstanceGenerator
from resources.grids.game_grid import GameGrid, EMPTY_SYMB

logger = logging.getLogger(__name__)

# Seed for reproducibility
random.seed(73128361)

N_INSTANCES = 2
LANGUAGE = 'en'

experiments = [
    # {
    #     'name': 'gs5x5_obj3',
    #     'grid_file': 'resources/grids/gs5x5_b2.json',
    #     'objects': 'CLP'
    # },
    {
        'name': 'gs7x7_obj3',
        'grid_file': 'resources/grids/gs7x7_b2.json',
        'objects': 'CLP'
    },
    # {
    #     'name': 'gs9x9_obj3',
    #     'grid_file': 'resources/grids/gs9x9_b3.json',
    #     'objects': 'CLP'
    # },
    # {
    #     'name': 'gs9x9_obj4',
    #     'grid_file': 'resources/grids/gs9x9_b3.json',
    #     'objects': 'DUMB'
    # },
    # {
    #     'name': 'gs11x11_obj3',
    #     'grid_file': 'resources/grids/gs11x11_b7.json',
    #     'objects': 'CLP'
    # },
    # {
    #     'name': 'gs11x11_obj5',
    #     'grid_file': 'resources/grids/gs11x11_b7.json',
    #     'objects': 'CHITW'
    # },
    # {
    #     'name': 'gs11x11_obj7',
    #     'grid_file': 'resources/grids/gs11x11_b7.json',
    #     'objects': 'POTSDAM'
    # },
    # {
    #     'name': 'gs11x11_obj9',
    #     'grid_file': 'resources/grids/gs11x11_b7.json',
    #     'objects': 'MAGISOULE'
    # },
    # {
    #     'name': 'gs11x16_obj7',
    #     'grid_file': 'resources/grids/gs11x16_b10.json',
    #     'objects': 'POTSDAM'
    # },
    # {
    #     'name': 'gs11x16_obj9',
    #     'grid_file': 'resources/grids/gs11x16_b10.json',
    #     'objects': 'MAGISOULE'
    # },
    # {
    #     'name': 'gs11x16_obj11',
    #     'grid_file': 'resources/grids/gs11x16_b10.json',
    #     'objects': 'ABCDEFGHIJK'
    # },
    # {
    #     'name': 'gs11x21_obj9',
    #     'grid_file': 'resources/grids/gs11x21_b15.json',
    #     'objects': 'MAGISOULE'
    # },
    # {
    #     'name': 'gs11x21_obj11',
    #     'grid_file': 'resources/grids/gs11x21_b15.json',
    #     'objects': 'ABCDEFGHIJK'
    # },
    # {
    #     'name': 'gs11x21_obj13',
    #     'grid_file': 'resources/grids/gs11x21_b15.json',
    #     'objects': 'ABCDEFGHIJKLM'
    # }
    {
        'name': 'gs11x21_obj3',
        'grid_file': 'resources/grids/gs11x21_b15.json',
        'objects': 'CLP'
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
                # Allow one penalty per object per player
                max_penalties = len(objects) * 2
                max_rounds = len(objects) * 4
                background = grid1.__str__(empty=True, show_coords=False)
                grid1.place_objects(objects)
                grid2.place_objects(objects)
                width, height = grid1.get_dimensions()
                game_instance = self.add_game_instance(experiment, instance_id)
                game_instance['language'] = LANGUAGE
                game_instance['width'] = width
                game_instance['height'] = height
                game_instance['lenient'] = True
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
                game_instance['invalid_response'] = self.load_template('resources/intermittent_prompts/invalid_response')
                game_instance['penalty_message'] = self.load_template('resources/intermittent_prompts/penalty_message')
                game_instance['penalty_counter'] = self.load_template('resources/intermittent_prompts/penalty_counter')
                game_instance['move_pattern'] = '(?P<head>.*)move\((?P<obj>[A-Z]), *(?P<x>\d+), *(?P<y>\d+)\)(?P<tail>.*)'
                game_instance['message_pattern'] = '(?P<head>.*)say\((?P<message>[^)]+)\)(?P<tail>.*)'
                # game_instance['message_pattern'] = '^say\((?P<message>[^)]+)\)$'
                # game_instance['terminate_question'] ='^say(finished?)$'
                game_instance['terminate_question'] = 'finished?'
                # game_instance['terminate_answer'] = '^say(finished)$'
                game_instance['terminate_answer'] = 'finished!'
                game_instance['restricted'] = ['[0-9]+', '\brows?', '\bcolumns?', '\bone\b', '\btwo\b', 
                                            '\bthree\b', '\bfour\b', '\bfive\b', '\bsix\b', '\bseven\b', 
                                            '\beight\b', '\bnine\b', '\bten\b', '\beleven\b', '\btwelve\b',
                                            '\bthirteen\b', '\bfirst\b', '\bsecond\b', '\bthird\b', '\bfourth\b',
                                            '\bfifth\b', '\bsixth\b', '\bseventh\b', '\beighth\b', '\bninth\b',
                                            '\btenth\b', '\beleventh\b', '\btwelfth\b', '\bthirteenth\b'
                                            ]
                # TODO: how to prohibit numbers in different languages?
                game_instance['parse_errors'] = self.load_json('resources/intermittent_prompts/parse_errors.json')[LANGUAGE]

    def initial_prompt(self, grid: GameGrid, max_penalties: int = 10) -> str:
        """
        Returns the initial prompt for the game.
        :param grid: The game grid
        :return: The initial prompt string
        """
        initial_prompt = Template(self.load_template('resources/initial_prompts/initial_prompt_dumb'))
        return initial_prompt.substitute(
            grid=str(grid),
            objects=grid.object_string(),
            empty_symbol=EMPTY_SYMB,
            max_penalties=max_penalties
        )

if __name__ == '__main__':
    CleanUpInstanceGenerator().generate()