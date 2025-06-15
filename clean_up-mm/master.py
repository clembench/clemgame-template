import os.path
import re
from typing import Dict, Tuple, List, Union
import logging
import numpy as np

from clemcore.backends import Model
from clemcore.clemgame import GameSpec, GameMaster, GameBenchmark, Player, DialogueGameMaster, GameScorer, \
    GameError, ParseError
from clemcore.clemgame.master import RuleViolationError
# from clemcore.utils import file_utils, string_utils

from resources.utils.PicState import PicState


logger = logging.getLogger(__name__)


class Cleaner(Player):
    def __init__(self, model: Model):
        super().__init__(model)
        self._custom_responses = ["say(Let's move the icon with a brain in a lightbulb.)", 
                                "say(Hello)", 
                                "move(A, 0, 0)"]

    def _custom_response(self, messages):
        response = self._custom_responses[np.random.randint(0, len(self._custom_responses))]
        return response

class MultiModalCleanUpMaster(DialogueGameMaster):
    def __init__(self, game_name: str, game_path: str, experiment: Dict, player_models: List[Model]):
        super().__init__(game_name, game_path, experiment, player_models)

    def _on_setup(self, **game_instance):
        # 0. init player
        # 1. each player has a PicState, 
        #    which contains the background and the initial icon state
        #    and is responsible for moving icons + generate base64 encoded image
        # 2. load and set init_context for player 1
        # 3. init game state flags: success? abort? finished?

        # [Question]: game design
        # now the background is the same for all instances in an experiment
        # is it necessary to get diff background for each instance in an experiment? 
        # -> probably no, otherwise there're too many variables to control
        background_path = self.experiment['background']

        self.player1 = Cleaner(self.player_models[0])
        self.player2 = Cleaner(self.player_models[1] if len(self.player_models) > 1 else self.player_models[0])

        self.player1.pic_state = PicState(background_path, game_instance['state1'])
        self.player2.pic_state = PicState(background_path, game_instance['state2'])
        
        # Temporary: bypass the template loaded by `instancegenerator.py` 
        # in case I want to change the prompt without affecting the instance state
        player1_init_text = self.load_template("resources/initial_prompts/player1")
        # player1_init_text = self.experiment['player1_initial_prompt']
        player1_init_image = self.player1.pic_state.draw()
        player1_init_context = self.__prep_text_and_image_prompt(player1_init_text, 
                                                                player1_init_image, 
                                                                content_only=False)    
        # [Question]: codebase
        # in `__call__` of `/clemcore/clemgame/player.py`, 
        # `initial_prompt` is glued to message history, preceding `initial_context`, 
        # what's the use of sending a message without getting an reply? 
        # is it a soft version of system message (role is still 'user'), can we set system message here?         
        self.add_player(self.player1, initial_context=player1_init_context)
        self.add_player(self.player2)
        
        # other attr/flags recording game state
        self.finished = False   # This is for negotiating the end of the game using `terminate_question` and `terminate_answer`
        self.success = False    # True if game finished regularly
        self.abort = False      # True if game is terminated because of rule violation or parse error        


    # [Question]: codebase
    # I don't see how image_url is prepared in multimodal reference game
    def __prep_text_and_image_prompt(self, text_content, image_url, content_only=False): 
        if not content_only:
        # used when init a player with initial_context
            return {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": text_content
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_url}"
                        }
                    }
                ]
            }
        else: 
        # used when directly calling `set_context_for`
            return [
                        {
                            "type": "text",
                            "text": text_content
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_url}"
                            }
                        }
                    ]

    def __other_player(self) -> Player:
        """
        Returns the player who will be next.
        """
        other_player_idx = (self._current_player_idx + 1) % len(self.players_by_names)
        return self.get_players()[other_player_idx]
    
    def __match_say(self, message): 
        # lenient impl, as long as the message contains `say(...)`, it is considered valid
        return re.compile(self.experiment['message_pattern']).search(message)

    def __match_move(self, message): 
        # lenient impl, as long as the message contains `move(...)`, it is considered valid
        return re.compile(self.experiment['move_pattern']).search(message)

    def _parse_response(self, player: Player, response: str) -> str:
        if bool(self.__match_move(response)): 
            return response
        elif bool(self.__match_say(response)):
            # normal say message:
            # TODO: check if say message contains coords
            return response            
        else: 
            self.abort = True
            raise ParseError(f"Invalid response format: {response}")

    def _on_parse_error(self, error: GameError):
        self.success = False
        self.abort = True

    def __process_say(self, player: Player, response: str, init: bool = False):
        """
        Process the say response from the player.
        If `init` is True, it means this is the initial call for the next player, 
        need to inject the response of the current player in the initial context for the next player.
        """
        if response == self.experiment['terminate_question']:
            self.finished = True

        if response == self.experiment['terminate_answer'] and self.finished:
            self.finished = True
            self.success = True
                
        # build the 1st part of feedback to current player (eg. your message has been relayed)                
        self.set_context_for(player, self.experiment['feedback_say'])

        # prep context for the next player
        to_inject = self.experiment['feedback_other_say'].replace("$$OTHER_PLAYER_SAY$$", response).replace("$$FEEDBACK_ENDING$$", self.experiment['feedback_ending'])
        
        if init:
            # Temporary: bypass the template loaded by `instancegenerator.py` 
            # in case I want to change the prompt without affecting the instance state
            player2_init_text = self.load_template("resources/initial_prompts/player2")
            player2_init_text = player2_init_text.replace("$$OTHER_PLAYER_COMMAND$$", to_inject)

            player2_init_image = self.player2.pic_state.draw()

            player2_init_context = self.__prep_text_and_image_prompt(player2_init_text, 
                                                                    player2_init_image, 
                                                                    content_only=True)            
            
            self.set_context_for(self.__other_player(), player2_init_context)
        else:
            # build the 2nd part of feedback to the next player
            self.set_context_for(self.__other_player(), to_inject)
        
    # TODO: enable re-prompting for move
    def __process_move(self, player: Player, response: str, init: bool = False):
        """
        Process the move response from the player.
        If `init` is True, it means this is the initial call for the next player, 
        need to inject the response of the current player in the initial context for the next player.
        """
        # alter the pic_state of the current player
        match = self.__match_move(response)
        obj = match.group("obj")
        x = match.group("x")
        y = match.group("y")
        player.pic_state.update(obj, int(x), int(y))

        # build the 1st part of feedback to current player (eg. the state of your pic is changed)
        feedback_text = self.experiment['feedback_move']
        feedback_image = player.pic_state.draw()
        context = self.__prep_text_and_image_prompt(feedback_text, 
                                                    feedback_image, 
                                                    content_only=True)   
        self.set_context_for(player, context)
        
        # prep context for the next player
        to_inject = self.experiment['feedback_other_move'].replace("$$FEEDBACK_ENDING$$", self.experiment['feedback_ending'])

        if init:
            # Temporary: bypass the template loaded by `instancegenerator.py` 
            # in case I want to change the prompt without affecting the instance state
            player2_init_text = self.load_template("resources/initial_prompts/player2")
            player2_init_text = player2_init_text.replace("$$OTHER_PLAYER_COMMAND$$", to_inject)

            player2_init_image = self.player2.pic_state.draw()

            player2_init_context = self.__prep_text_and_image_prompt(player2_init_text, 
                                                                    player2_init_image, 
                                                                    content_only=True)            
            
            self.set_context_for(self.__other_player(), player2_init_context)            
        else: 
            # build the 2nd part of feedback to the next player
            self.set_context_for(self.__other_player(), to_inject)


    def _advance_game(self, player: Player, parsed_response: str):
        """
        Args: 
            - parsed_response: not really parsed, rather, **validated** response from the player
        """
        # Two cases: 
            # 0. if just finished 1st prompt to player1, 
            #    next up is 1st prompt to player2, 
            #    need to inject player1's command into the init context for player2,
            # 1. if each player has been prompted at least once
        # in both cases: 
            # - build (part of) feedback to current player;
            #   eg. "Your message has been relayed to the other player"
            #   eg. "The state of your pic has been changed"
            # - build (part of) feedback to the othe palyer: 
            #   eg. "The other player said: <parsed_response>"
            #   eg. "The other player moved an icon on their picture"


        if not parsed_response:
            raise RuleViolationError
        
        # The next player hasn't been prompted, need to init their context
        if self.__other_player()._is_initial_call: 
            if bool(self.__match_say(parsed_response)):
                self.__process_say(player, parsed_response, init=True)

            elif bool(self.__match_move(parsed_response)):
                self.__process_move(player, parsed_response, init=True)

            else: 
                raise GameError(f"Invalid response format: {parsed_response}")
        # All players have been prompted at least once
        else: 
            if bool(self.__match_say(parsed_response)):
                self.__process_say(player, parsed_response, init=False)            

            if bool(self.__match_move(parsed_response)):
                self.__process_move(player, parsed_response, init=False)

        print("===== at the end of _advance_game =====")
        print(f"player.name: {player.name}")
        print(f"response: {parsed_response}") 
        print(f"[DEBUG] log_event: {self._game_recorder.__class__}")
           

    def _does_game_proceed(self):
        if self.success or self.abort: 
            return False
        
        return True

    def compute_turn_score(self):
        return 1 if self.success else 0

    def compute_episode_score(self):
        if self.success:
            return 100 / (self.current_round + 1)  # zero-based
        return 0

    def _on_after_game(self):
        if self.success:
            self.log_key('success', 'true')
        else:
            self.log_key('success', 'false')


class SomeGameScorer(GameScorer):
    def __init__(self, game_name: str, experiment: Dict, game_instance: Dict):
        super().__init__(game_name, experiment, game_instance)

    def score_turns(self, episode_interactions: Dict) -> None:
        """ Turn-level scores """
        for turn_idx in range(len(episode_interactions)):
            for event in episode_interactions[turn_idx]:
                if event['type'] == 'player_response':
                    self.log_turn_score(turn_idx, 'response_received', 1)

    def log_main_score(self, episode_interactions: Dict):
        if episode_interactions['success'] == 'true':
            self.log_episode_score("BENCH_SCORE", 100)
        elif episode_interactions['success'] == 'false':
            self.log_episode_score("BENCH_SCORE", 0)


class SomeGameBenchmark(GameBenchmark):

    def __init__(self, game_spec: GameSpec):
        super().__init__(game_spec)

    def create_game_master(self, experiment: Dict, player_models: List[Model]) -> GameMaster:
        return MultiModalCleanUpMaster(self.game_name, self.game_path, experiment, player_models)

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return SomeGameScorer(self.game_name, experiment, game_instance)

