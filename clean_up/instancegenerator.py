"""Template script for instance generation.

usage:
python3 instancegenerator.py
Creates instance.json file in ./in

"""
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
LANGUAGES = ['en']

experiments = [
    {
        'name': 'gs7x7_obj3',
        'grid_file': 'resources/grids/gs7x7_b2.json',
        'objects': 'CLP'
    },
    {
        'name': 'gs7x7_obj4',
        'grid_file': 'resources/grids/gs7x7_b2.json',
        'objects': 'DUMB'
    },
    {
        'name': 'gs9x9_obj4',
        'grid_file': 'resources/grids/gs9x9_b3.json',
        'objects': 'DUMB'
    },
    {
        'name': 'gs9x9_obj5',
        'grid_file': 'resources/grids/gs9x9_b3.json',
        'objects': 'CHITW'
    },
    {
        'name': 'gs11x11_obj5',
        'grid_file': 'resources/grids/gs11x11_b7.json',
        'objects': 'CHITW'
    },
    {
        'name': 'gs11x11_obj7',
        'grid_file': 'resources/grids/gs11x11_b7.json',
        'objects': 'POTSDAM'
    }
]

class CleanUpInstanceGenerator(GameInstanceGenerator):
    def __init__(self):
        super().__init__(os.path.dirname(__file__))

    def on_generate(self):
        for LANGUAGE in LANGUAGES:
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
                    game_instance['p1_initial_prompt'] = self.initial_prompt(grid1, language=LANGUAGE, max_penalties=10) + self.load_template(f'resources/initial_prompts/{LANGUAGE}/p1_start')
                    game_instance['p2_initial_prompt'] = self.initial_prompt(grid2, language=LANGUAGE, max_penalties=10) + self.load_template(f'resources/initial_prompts/{LANGUAGE}/p2_start')
                    game_instance['new_turn'] = self.load_template(f'resources/intermittent_prompts/{LANGUAGE}/new_turn')
                    game_instance['new_turn_move'] = self.load_template(f'resources/intermittent_prompts/{LANGUAGE}/new_turn_move')
                    game_instance['invalid_response'] = self.load_template(f'resources/intermittent_prompts/{LANGUAGE}/invalid_response')
                    game_instance['penalty_message'] = self.load_template(f'resources/intermittent_prompts/{LANGUAGE}/penalty_message')
                    game_instance['penalty_counter'] = self.load_template(f'resources/intermittent_prompts/{LANGUAGE}/penalty_counter')
                    game_instance['message_relay'] = self.load_template(f'resources/intermittent_prompts/{LANGUAGE}/message_relay')

                    keywords = self.load_json('resources/keywords.json')[LANGUAGE]
                    game_instance['move_pattern'] = f"(?P<head>.*){keywords['move_command']}\((?P<obj>[A-Z]), *(?P<x>\d+), *(?P<y>\d+)\)(?P<tail>.*)"
                    game_instance['message_pattern'] = f"(?P<head>.*){keywords['message_command']}\((?P<message>[^)]+)\)(?P<tail>.*)"
                    game_instance['terminate_question'] = keywords['terminate_question']    # 'finished?'
                    game_instance['terminate_answer'] = keywords['terminate_answer']        # 'finished!'
                    game_instance['restricted'] = self.load_json('resources/restricted_patterns.json')[LANGUAGE]
                    game_instance['parse_errors'] = self.load_json('resources/parse_errors.json')[LANGUAGE]

                    game_instance['move_messages'] = self.load_json('resources/move_messages.json')[LANGUAGE]

    def initial_prompt(self, grid: GameGrid, language: str, max_penalties: int = 10) -> str:
        """
        Returns the initial prompt for the game.
        :param grid: The game grid
        :return: The initial prompt string
        """
        initial_prompt = Template(self.load_template(f'resources/initial_prompts/{language}/initial_prompt_dumb'))
        return initial_prompt.substitute(
            grid=str(grid),
            objects=grid.object_string(),
            empty_symbol=EMPTY_SYMB,
            max_penalties=max_penalties
        )

if __name__ == '__main__':
    CleanUpInstanceGenerator().generate()
