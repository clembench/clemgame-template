"""
Generate game instances for the Multimodal CleanUp game, making use of the icons in 'resources/icons/' 
and the backgrounds in 'resources/backgrounds/'. 

To download more icons, see 'resources/get_icons.py'.

usage:
python instancegenerator.py
Creates instance.json file in ./in

"""
import os
import random
import math
from PIL import Image

from clemcore.clemgame import GameInstanceGenerator


"""
6 variations of the game: 
- dimension 1: diff type of icons (normal, abstract, similar)
    * when normal, randomly select N normal category, from each category pick 1
    * when similar, randomly select 1 normal category, from it select N pic
    * when abstract, randomly select N abstract icons  
- dimension 2: diff number of icons (a few, many)
"""
# number of instances per experiment
N_INSTANCES = 10 

# logger = logging.getLogger(__name__)

random.seed(73128361)  

class CleanUPMultiModalInstanceGenerator(GameInstanceGenerator):

    def __init__(self):
        super().__init__(os.path.dirname(__file__))

    def on_generate(self):
        # for each experiment type, 
            # 1. load background

            # 2. randomly choose N_ICONS categories of icons, 
            #    and for each category, randomly choose 1 of the icons

            # 3. shuffle the selected icons, 
            #    assemble two state per instance: [ { id, path, coord }, .. ]

        # for e in ["small_normal", "big_normal", "small_abstract", "small_similar"]:
        for e in ["small_normal"]:
            N_ICONS = 5
            print(f"Adding experiment of type {e}")

            experiment = self.add_experiment(e)
            experiment["player1_initial_prompt"] = self.load_template("resources/initial_prompts/player1")
            experiment["player2_initial_prompt"] = self.load_template("resources/initial_prompts/player2")

            experiment['feedback_say'] = self.load_template("resources/intermittent_prompts/feedback_say")
            experiment['feedback_move'] = self.load_template("resources/intermittent_prompts/feedback_move")
            experiment['feedback_other_say'] = self.load_template("resources/intermittent_prompts/feedback_other_say")
            experiment['feedback_other_move'] = self.load_template("resources/intermittent_prompts/feedback_other_move")
            experiment['feedback_ending'] = self.load_template("resources/intermittent_prompts/feedback_ending")

            experiment['terminate_question'] = "say(finished?)"
            experiment['terminate_answer'] = "say(finished!)"
            
            experiment['message_pattern'] = "say\\((?P<message>.+)\\)"
            experiment['move_pattern'] = "move\\((?P<obj>[A-Z]),\\s*(?P<x>\\d+),\\s*(?P<y>\\d+)\\)"

            background_path = self._get_random_file('resources/backgrounds/')
            experiment["background"] = background_path

            bg_img = Image.open(background_path)
            bg_size = bg_img.size

            target_id = 0
            while target_id < N_INSTANCES:
                icon_directories = self._get_random_subdir("resources/icons/", N_ICONS, ["abstract"])
                icon_paths = [self._get_random_file(d) for d in icon_directories]

                state1 = self._get_random_icon_state(icon_paths, bg_size)
                state2 = self._get_random_icon_state(icon_paths, bg_size)

                game_instance = self.add_game_instance(experiment, target_id)
                game_instance["state1"] = state1
                game_instance["state2"] = state2
                target_id += 1

    def _get_random_file(self, directory, file_extension='png'): 
        files = [f for f in os.listdir(directory) if f.lower().endswith(file_extension)]
        if not files:
            raise FileNotFoundError("No PNG files found in the directory.")
        return os.path.join(directory, random.choice(files))

    def _get_random_subdir(self, directory, k=1, exceptions=[]):
        subdirs = [os.path.join(directory, d) for d in os.listdir(directory)
                    if os.path.isdir(os.path.join(directory, d)) and d not in exceptions
                ]
        if not subdirs:
            raise FileNotFoundError("No subdirectories found.")
        return random.sample(subdirs, k=k) if k > 1 else random.choice(subdirs)

    def _get_random_icon_state(self, icon_paths, bg_size): 
        random.shuffle(icon_paths)
        bg_width, bg_height = bg_size

        state = []
        occupied = set()
        for idx, icon_path in enumerate(icon_paths):
            id = chr(ord('A') + idx) # use A,B,C,D.. as ID
            img = Image.open(icon_path)
            coord = self._get_random_nonoverlapping_coord(img.size, bg_width, bg_height, occupied)
            if coord is None:
                print(f"Warning: Skipping icon {icon_path} due to space constraints.")
                continue

            occupied.add(coord)
            state.append({"id": id, "icon_path": icon_path, "coord": coord})
        return state

    def _get_random_nonoverlapping_coord(self, img_size, bg_width, bg_height, occupied):
        w, h = img_size
        step = 100

        min_x = math.ceil(w / 2 / step) * step
        max_x = (bg_width - w // 2) // step * step
        min_y = math.ceil(h / 2 / step) * step
        max_y = (bg_height - h // 2) // step * step

        valid_positions = [
            (x, y)
            for x in range(min_x, max_x + 1, step)
            for y in range(min_y, max_y + 1, step)
            if (x, y) not in occupied
        ]

        return random.choice(valid_positions) if valid_positions else None        
    


if __name__ == '__main__':
    CleanUPMultiModalInstanceGenerator().generate()
