"""
Generate game instances for the Multimodal CleanUp game, making use of the icons in 'resources/icons/' 
and the backgrounds in 'resources/backgrounds/'. 

To download more icons, see 'resources/get_icons.py'.

usage:
python instancegenerator.py
Creates instance.json file in ./in

"""
import os
import re
import random
import math
import copy

from string import Template
from PIL import Image
from typing import List

from resources.utils.constant import ICON_WIDTH
from clemcore.clemgame import GameInstanceGenerator


"""
6 variations of the game: 
- dimension 1: diff type of icons (normal, abstract, similar)
    * when normal, randomly select N normal category, from each category pick 1 icon
    * when similar, randomly select 1 normal category, from it select N icons
    * when abstract, randomly select 1 abstract category, from it select N icons
- dimension 2: diff number of icons (N = 5, 9)
"""

LANGUAGES = ['en']
# number of instances per experiment
# N_INSTANCES = 10 
N_INSTANCES = 2
# number of icons per instance; 2 is only for dev purpose
ICON_NUM_OPTIONS = [2]
# ICON_NUM_OPTIONS = [5, 9]
# configurations for each icon type
ICON_TYPE_CONFIGS = {
            "normal": {
                "category": "normal", 
                "n_subcategories": "$$ICON_NUM$$",
                "n_icons_per_subcategory": 1,
            }, 
            # "similar": {  # maybe change to "normal_similar"
            #     "category": "normal", 
            #     "n_subcategories": 1,
            #     "n_icons_per_subcategory": "$$ICON_NUM$$",
            # }, 
            # # across different sub-categories of abstract, 
            # # it's easy to distinguish the icons, 
            # # so we only need to select one sub-category,
            # "abstract": {  # maybe change to "abstract_similar"
            #     "category": "abstract",
            #     "n_subcategories": 1,
            #     "n_icons_per_subcategory": "$$ICON_NUM$$",
            # }   
        }

ICON_METADATA_PATH = "resources/icons/metadata.json"

# logger = logging.getLogger(__name__)

random.seed(73128361)  

class CleanUpMultiModalInstanceGenerator(GameInstanceGenerator):

    def __init__(self):
        super().__init__(os.path.dirname(__file__))

    def on_generate(self):
        for LANGUAGE in LANGUAGES:
            # for each experiment type, 
                # 1. load background

                # 2. randomly choose N_ICONS categories of icons, 
                #    and for each category, randomly choose 1 of the icons

                # 3. shuffle the selected icons, 
                #    assemble two state per instance: [ { id, path, coord }, .. ]

            for icon_type, icon_type_config in ICON_TYPE_CONFIGS.items():
                for icon_num in ICON_NUM_OPTIONS:
                    config = copy.deepcopy(icon_type_config)
                    config = {key: icon_num if val == "$$ICON_NUM$$" else val for key, val in config.items() }
                    e = f"{icon_type}_{icon_num}"
                    
                    print(f"===== Adding experiment of type {e} =====")
                    print(config)

                    experiment = self.add_experiment(e)

                    for instance_id in range(N_INSTANCES):
                        game_instance = self.add_game_instance(experiment, instance_id)

                        game_instance['max_rounds'] = icon_num * 3
                        game_instance['max_penalties'] = icon_num * 2
                        game_instance['lenient'] = True
                        game_instance["p1_initial_prompt"] = Template(self.load_template(f"resources/initial_prompts/{LANGUAGE}/initial_prompt")).substitute(max_rounds=str(game_instance['max_rounds'])) + self.load_template(f'resources/initial_prompts/{LANGUAGE}/p1_start')
                        game_instance["p2_initial_prompt"] = Template(self.load_template(f"resources/initial_prompts/{LANGUAGE}/initial_prompt")).substitute(max_rounds=str(game_instance['max_rounds'])) + self.load_template(f'resources/initial_prompts/{LANGUAGE}/p2_start')
                        game_instance['new_turn'] = self.load_template(f"resources/intermittent_prompts/{LANGUAGE}/new_turn")
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

                        # This is message_relay
                        game_instance['feedback_say'] = self.load_template(f"resources/intermittent_prompts/{LANGUAGE}/feedback_say")
                        # "The state of your picture is updated and attached."
                        game_instance['feedback_move'] = self.load_template(f"resources/intermittent_prompts/{LANGUAGE}/feedback_move")
                        # new_turn
                        game_instance['feedback_other_say'] = self.load_template(f"resources/intermittent_prompts/{LANGUAGE}/feedback_other_say")
                        # new_turn_move
                        game_instance['feedback_other_move'] = self.load_template(f"resources/intermittent_prompts/{LANGUAGE}/feedback_other_move")
                        # "Now, please give your command."
                        game_instance['feedback_ending'] = self.load_template(f"resources/intermittent_prompts/{LANGUAGE}/feedback_ending")

                        keywords = self.load_json('resources/keywords.json')[LANGUAGE]
                        game_instance['move_pattern'] = f"(?P<head>.*){keywords['move_command']}\((?P<obj>[A-Z]), *(?P<x>\d+), *(?P<y>\d+)\)(?P<tail>.*)"
                        game_instance['message_pattern'] = f"(?P<head>.*){keywords['message_command']}\((?P<message>[^)]+)\)(?P<tail>.*)"
                        game_instance['terminate_question'] = keywords['terminate_question']    # 'finished?'
                        game_instance['terminate_answer'] = keywords['terminate_answer']        # 'finished!'
                        game_instance['restricted'] = self.load_json('resources/restricted_patterns.json')[LANGUAGE]
                        game_instance['parse_errors'] = self.load_json('resources/parse_errors.json')[LANGUAGE]

                        game_instance['move_messages'] = self.load_json('resources/move_messages.json')[LANGUAGE]

                        background_path = self._get_random_file(os.path.join("resources", "backgrounds"), n=1)[0]
                        game_instance["background"] = background_path

                        bg_img = Image.open(background_path)
                        bg_size = bg_img.size

                        category = config["category"]
                        n_subcategories = config["n_subcategories"]
                        n_icons_per_subcategory = config["n_icons_per_subcategory"]

                        print(f"Category: {category}, n_subcategories: {n_subcategories}, n_icons_per_subcategory: {n_icons_per_subcategory}")

                        metadata = self.load_json(ICON_METADATA_PATH)

                        assert n_subcategories <= len(metadata[category]), \
                            f"n_subcategories ({n_subcategories}) must be less than or equal to the number of subcategories in {category} ({len(metadata[category])})"

                        subcategories = random.sample(list(metadata[category].keys()), n_subcategories)

                        # [ {id, name, url}, ... ]
                        chosen_icons = []
                        for sub in subcategories:
                            assert n_icons_per_subcategory <= len(metadata[category][sub]), \
                                f"n_icons_per_subcategory ({n_icons_per_subcategory}) must be less than or equal to the number of icons in subcategory {sub} ({len(metadata[category][sub])})"
                            
                            for icon in random.sample(metadata[category][sub], n_icons_per_subcategory):
                                chosen_icons.append(icon)
                    
                        # chosen_icons = [icon
                        #                 for sub in subcategories 
                        #                     for icon in random.sample(metadata[category][sub], n_icons_per_subcategory) 
                        # ]

                        # icon_sub_dirs = self._get_random_subdir(os.path.join("resources", "icons", category), 
                        #                                         n_subcategories)
                        
                        # icon_paths = [f for d in icon_sub_dirs for f in self._get_random_file(d)]

                        # [ {id, coord, name, url, freepik_id} ]
                        state1 = self._get_random_icon_state(chosen_icons, bg_size)
                        state2 = self._get_random_icon_state(chosen_icons, bg_size)

                        game_instance["state1"] = state1
                        game_instance["state2"] = state2

    def _get_random_file(self, directory, n=1, file_extension='png') -> List[str]: 
        files = [f for f in os.listdir(directory) if f.lower().endswith(file_extension)]
        
        if not files:
            raise FileNotFoundError(f"No .{file_extension} files found in the directory.")
        
        assert n <= len(files), f"n must be less than or equal to the number of files in the directory ({len(files)})"

        chosen_files = random.sample(files, n) if n > 1 else [random.choice(files)]
        
        return [os.path.join(directory, p) for p in chosen_files]

    def _get_random_subdir(self, directory, k=1) -> List[str]:
        subdirs = [os.path.join(directory, d) 
                    for d in os.listdir(directory)
                        if os.path.isdir(os.path.join(directory, d))]
        if not subdirs:
            raise FileNotFoundError("No subdirectories found.")
        
        assert k < len(subdirs), "k must be less than the number of subdirectories"
        
        return random.sample(subdirs, k=k) if k > 1 else [random.choice(subdirs)]

    def _get_random_icon_state(self, chosen_icons, bg_size): 
        random.shuffle(chosen_icons)
        bg_width, bg_height = bg_size

        rand_coords = self._get_random_nonoverlapping_coords(ICON_WIDTH, 
                                                        bg_width, 
                                                        bg_height, 
                                                        len(chosen_icons))

        pattern = re.compile(rf"\.com/{ICON_WIDTH}/")
        state = []

        for idx, icon in enumerate(chosen_icons):
            # assert the icon_width bit in URL is ICON_WIDTH
            assert re.search(pattern, icon['url']) is not None

            id = chr(ord('A') + idx) # use A,B,C,D.. as ID
            
            state.append({"id": id, "coord": rand_coords[idx], **icon})

        return state

    def _get_random_nonoverlapping_coords(self, icon_width, bg_width, bg_height, n):
        w, h = icon_width, icon_width # icons are square
        step = (w // 50) * 50 # the largest multiple of 50 that is less than or equal to w

        min_x = math.ceil(w / 2 / step) * step
        max_x = (bg_width - w // 2) // step * step
        min_y = math.ceil(h / 2 / step) * step
        max_y = (bg_height - h // 2) // step * step

        valid_positions = [
            (x, y)
            for x in range(min_x, max_x + 1, step)
            for y in range(min_y, max_y + 1, step)
        ]
        assert n <= len(valid_positions)
        return random.sample(valid_positions, n)
    


if __name__ == '__main__':
    CleanUpMultiModalInstanceGenerator().generate()
