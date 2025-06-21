import os.path
import json
import re
import logging
import numpy as np
from typing import Dict, Tuple, List, Union
from collections import defaultdict

from clemcore.backends import Model
from clemcore.clemgame import GameSpec, GameMaster, GameBenchmark, Player, DialogueGameMaster, GameScorer, GameError, ParseError
from clemcore.clemgame.master import RuleViolationError
from clemcore.clemgame.metrics import METRIC_ABORTED, METRIC_SUCCESS, METRIC_LOSE, BENCH_SCORE
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

class MetricHolder: 
    """
    This score computes how consistent the moves are, 
    and could indicate how good the model is at describing and differentiating to target at the correct icon,
    that it agreed to move with the other player.
    It is computed episode-wise, and at GameMaster level (because both players contribute to it.)

    Example: 
        player 1: move A (1)
        player 2: move A (2)
        player 1: move B (3) 
        player 2: move B (4)  
    From (1) to (2) and from (3) to (4), the players are moving consistently. 
    They only shifted the focused object from (2) to (3). 

    Conversely, when the moving sequence is like
        player 1: move A
        player 2: move C
        player 1: move B
        player 2: move A
    Then between any two consecutive moves, they are always shifting the focus.
    """
    def __init__(self, n_icons, max_rounds, freepik_id_set, game_master): 
        # self.moves: [ (player, { id, coord, name, url, freepik_id, img } ), ... ]
        self.moves = []
        self.shifts = 0

        self.min_shifts = n_icons - 1
        self.max_shifts = max_rounds * 2
        self.ids_set = freepik_id_set
        self.game_master = game_master

    def add_move(self, move_info): 
        """
        move_info: a tuple: (player, { id, coord, name, url, freepik_id, img } )
        """
        player, icon_element = move_info

        freepik_id = icon_element['freepik_id']
        
        # increment `self.shifts` only when the current id differs from last moved id
        if len(self.moves) != 0: 
            prev_player, prev_icon = self.moves[-1] 
            
            if freepik_id != prev_icon['freepik_id']: 
                print(f"Shift of focus from freepik_id {prev_icon['freepik_id']} to {freepik_id}")
                self.game_master.log_to_self("log move", f"Shift of focus from freepik_id {prev_icon['freepik_id']} to {freepik_id}")
                self.shifts += 1
        
        self.moves.append(move_info)

    def compute_consistency_score(self): 
        if self.shifts > self.max_shifts: 
            return 0
        
        min_max_normed = (self.shifts - self.min_shifts) / (self.max_shifts - self.min_shifts)
        # quadratically reduce the score
        # eg. when self.shifts is 50% towards self.maximum, 
        #     the score is 0.25
        # return (1 - min_max_normed) ** 2
        score = 1 - min_max_normed
        return score
    
    def compute_coverage_score(self): 
        moved_set = set([move[1]['freepik_id'] for move in self.moves])
        assert moved_set <= self.ids_set, "The moved icons should be a subset of all icons."

        # quadratically reduce the score when some icons are not touched by either of the players
        # eg. when half of the icons are not touched, 
        #     the score is 0.25
        return (len(moved_set) / len(self.ids_set)) ** 2
            


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

        self.max_rounds = self.experiment['max_rounds']
        self.message_pattern = self.experiment['message_pattern']
        self.move_pattern = self.experiment['move_pattern']
        self.should_pass_turn = True

        n_icons = len(game_instance['state1'])
        freepik_id_set = set(ele['freepik_id'] for ele in game_instance['state1'])
        self.metric_holder = MetricHolder(n_icons, self.max_rounds, freepik_id_set, self)

        self.player1 = Cleaner(self.player_models[0])
        self.player2 = Cleaner(self.player_models[1] if len(self.player_models) > 1 else self.player_models[0])

        background_path = self.experiment['background']
        self.player1.pic_state = PicState(background_path, game_instance['state1'])
        self.player2.pic_state = PicState(background_path, game_instance['state2'])
        
        # Temporary: bypass the template loaded by `instancegenerator.py` 
        # in case I want to change the prompt without affecting the instance state
        player1_init_text = self.load_template("resources/initial_prompts/player1").replace("$$MAX_ROUNDS$$", str(self.max_rounds))
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

        
        self.finished = False   # This is for negotiating the end of the game using `terminate_question` and `terminate_answer`
        self.success = False    # True if game finished regularly
        self.abort = False      # True if game is terminated because of rule violation or parse error        
        self.lose = False       # True if game exceeds max_rounds


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
        return re.compile(self.message_pattern).search(message)

    def __match_move(self, message): 
        return re.compile(self.move_pattern).search(message)

    def __match_multi(self, message): 
        match_says = list(re.compile(self.message_pattern).finditer(message))
        match_moves = list(re.compile(self.move_pattern).finditer(message))

        return len(match_says) + len(match_moves) > 1

    def _parse_response(self, player: Player, response: str) -> str:
        stripped_response = response.replace('`', '').replace('\n', ' ').strip()

        print(f"===== {player.name} =====")
        print(f"response: {response}") 
        print(f"stripped response: {stripped_response}") 

        if self.__match_multi(stripped_response): 
            # return 
            self.log_to_self("parsing warning", f"response matches multiple command:\n{response}")
            return defaultdict(lambda: False, { "response": stripped_response, "isMulti": True} )
        elif bool(self.__match_say(stripped_response)): 
            # normal say message:
            # TODO: check if say message contains coords
            self.log_to_self("parsing", f"response matches say:\n{response}")
            return defaultdict(lambda: False, { "response": stripped_response, "isSay": True} )
        elif bool(self.__match_move(stripped_response)):
            self.log_to_self("parsing", f"response matches move:\n{response}")
            return defaultdict(lambda: False, { "response": stripped_response, "isMove": True} )
        else: 
            self.log_to_self("parsing error", f"response matches neither say nor move:\n{response}")
            raise ParseError(f"Invalid response format: {response}")

    def _on_parse_error(self, error: GameError):
        self.success = False
        self.abort = True

    def __process_say(self, player: Player, response: str, other_init: bool = False) -> bool:
        """
        Process the say response from the player.
        If `init` is True, it means this is the initial call for the next player, 
        need to inject the response of the current player in the initial context for the next player.

        Returns: a boolean indicating whether GM should pass turn to the next player or not.
        """
        # Temp: losen the ending condition
        # # if response == self.experiment['terminate_question']:
        if self.experiment['terminate_question'] in response:
            self.finished = True

        # Temp: losen the ending condition
        # if response == self.experiment['terminate_answer'] and self.finished:
        if self.experiment['terminate_answer'] in response and self.finished:
            self.finished = True
            self.success = True
        # feedback to current player about their own command (eg. your message has been relayed)                
        player._messages.append(dict(role='user', content=self.experiment['feedback_say']))

        # prep context for the next player
        to_inject = self.experiment['feedback_other_say'].replace("$$OTHER_PLAYER_SAY$$", response).replace("$$FEEDBACK_ENDING$$", self.experiment['feedback_ending'])
        
        if other_init:
            # Temporary: bypass the template loaded by `instancegenerator.py` 
            # in case I want to change the prompt without affecting the instance state
            player2_init_text = self.load_template("resources/initial_prompts/player2").replace("$$MAX_ROUNDS$$", str(self.max_rounds))
            player2_init_text = player2_init_text.replace("$$OTHER_PLAYER_COMMAND$$", to_inject)

            player2_init_image = self.player2.pic_state.draw()

            player2_init_context = self.__prep_text_and_image_prompt(player2_init_text, 
                                                                    player2_init_image, 
                                                                    content_only=True)            
            
            self.set_context_for(self.__other_player(), player2_init_context)
        else:
            # feedback to the other player about current player's command (eg. the other player said this to you: <response>)
            self.set_context_for(self.__other_player(), to_inject)
        
        # indicate that the turn should be passed to the next player
        return True 

    # TODO: enable re-prompting for move
    def __process_move(self, player: Player, response: str, other_init: bool = False):
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

        icon_element = player.pic_state.get_element_by_id(obj)
        if icon_element:
            player.pic_state.update(obj, int(x), int(y))
            self.metric_holder.add_move((player, icon_element))

        distance_after_move = player.pic_state.get_pairwise_distance(self.__other_player().pic_state, toRound=True)

        # build the 1st part of feedback to current player (eg. the state of your pic is changed and attached)
        feedback_text = self.experiment['feedback_move']
        feedback_image = player.pic_state.draw()
        content = self.__prep_text_and_image_prompt(f"{player.name} has moved the image", 
                                                    feedback_image, 
                                                    content_only=True)   
        
        # adding visual feedback lead to this error, I doubt input token overflow
        # Error code: 400 - {'error': {'message': 'Provider returned error', 'code': 400, 'metadata': {'raw': '{"error":{"code":"invalid_parameter_error","param":null,"message":"<400> InternalError.Algo.InvalidParameter: Range of input length should be [1, 129024]","type":"invalid_request_error"},"id":"chatcmpl-262914be-bc46-9270-9a8c-9940431806a3","request_id":"262914be-bc46-9270-9a8c-9940431806a3"}', 'provider_name': 'Alibaba'}}, 'user_id': 'user_2x4zp7KKD00ihTJC2Ox7pxsiwT2'}
        # player._messages.append(dict(role='user', content=content))
        player._messages.append(dict(role='user', content="Your picture has been updated."))
        
        # prep context for the next player
        to_inject = self.experiment['feedback_other_move'].replace("$$FEEDBACK_ENDING$$", self.experiment['feedback_ending'])

        if other_init:
            # Temporary: bypass the template loaded by `instancegenerator.py` 
            # in case I want to change the prompt without affecting the instance state
            player2_init_text = self.load_template("resources/initial_prompts/player2").replace("$$MAX_ROUNDS$$", str(self.max_rounds))
            player2_init_text = player2_init_text.replace("$$OTHER_PLAYER_COMMAND$$", to_inject)

            player2_init_image = self.player2.pic_state.draw()

            player2_init_context = self.__prep_text_and_image_prompt(player2_init_text, 
                                                                    player2_init_image, 
                                                                    content_only=True)            
            
            self.set_context_for(self.__other_player(), player2_init_context)            
        else: 
            # build the 2nd part of feedback to the next player
            self.set_context_for(self.__other_player(), to_inject)

        # logs        
        icon_info = player.pic_state.get_element_by_id(obj)
        if not icon_info:
            self.log_to_self("log move", f"{player.name} attempted to move an icon that does not exist: {obj}")
        keys_to_keep = ['name', 'freepik_id', 'id']
        icon_info = {k: v for k, v in icon_info.items() if k in keys_to_keep}
        self.log_to_self("log move", f"{player.name} attempted to move the icon {icon_info}")

        self.log_to_self("log move", content)

        self.log_to_self("log distance", f"after move:\npairwise distance: {json.dumps(distance_after_move, indent=4)}") 
        self.log_to_self("log distance", f"after move:\ntotal distance: {round(sum(distance_after_move.values()), 2)}") 

        # indicating whether should pass turn to the other player
        return True

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
            # - build (part of) feedback to the other player: 
            #   eg. "The other player said this to you: <parsed_response>"
            #   eg. "The other player moved an icon on their picture"

        if not parsed_response:
            raise RuleViolationError
        
        if parsed_response['isMulti']: 
            feedback = f"Warning: Invalid command. Use only one command per turn, either say or move. Now send your command again."
            print(f"--- reprompting: GM to {player.name}---")
            print(f"feedback: {feedback}")             
            self.set_context_for(player, feedback)
            self.should_pass_turn = False
        
        # The next player hasn't been prompted, need to init their context
        other_init = self.__other_player()._is_initial_call

        if parsed_response['isSay']:
            self.should_pass_turn = self.__process_say(player, parsed_response['response'], other_init=other_init)
            # self.__process_say(player, parsed_response['response'], other_init=other_init)


        elif parsed_response['isMove']:
            self.should_pass_turn = self.__process_move(player, parsed_response['response'], other_init=other_init)
            # self.__process_move(player, parsed_response['response'], other_init=other_init)

        else: 
            raise GameError(f"Invalid response format: {parsed_response}")


    def _should_pass_turn(self): 
        return self.should_pass_turn
    
    def _does_game_proceed(self):
        if self.success or self.abort: 
            return False
        
        if self.current_round >= self.max_rounds:
            self.lose = True
            self.success = False
            return False
        
        return True

    def compute_turn_score(self):
        return 1 if self.success else 0

    def compute_episode_score(self):
        if self.abort or self.lose:
            return {"distance_sum": float('inf'), "distance_score": 0, "consistency_score": 0, "coverage_score": 0}

        p1 = self.player1.pic_state
        p2 = self.player2.pic_state
        distance_sum = p1.distance_sum(p2)
        distance_score = p1.distance_score(p2)

        consistency_score = self.metric_holder.compute_consistency_score()
        coverage_score = self.metric_holder.compute_coverage_score()

        final_score = distance_score * consistency_score * coverage_score 

        scores = {
                    "distance_sum": distance_sum, 
                    "distance_score": distance_score,
                    "consistency_score": consistency_score,    
                    "coverage_score": coverage_score,
                    "final_score": final_score
                }
        print("in compute_episode_score")
        print(scores)
        return scores


    def _on_after_game(self):
        scores = self.compute_episode_score()

        # log_key to `interaction.json`
        self.log_key(METRIC_ABORTED, int(self.abort))
        self.log_key(METRIC_LOSE, int(self.lose))
        self.log_key(METRIC_SUCCESS, int(self.success))     
        self.log_key('distance_sum', str(scores['distance_sum']))
        self.log_key('distance_score', scores['distance_score'])
        self.log_key('consistency_score', scores['consistency_score'])
        self.log_key('coverage_score', scores['coverage_score'])
        self.log_key('final_score', scores['final_score'])
        
        # log to display in transcript``
        self.log_to_self("log metric", f"Success: {self.success}; Aborted: {self.abort}; Lose: {self.lose}")
        self.log_to_self("log metric", f"total distance:\n{ round(scores['distance_sum'], 2) }") 
        self.log_to_self("log metric", f"distance score:\n{ round(scores['distance_score'], 2) }") 
        self.log_to_self("log metric", f"consistency score:\n{ round(scores['consistency_score'], 2) }")
        self.log_to_self("log metric", f"coverage score:\n{ round(scores['coverage_score'], 2) }")       
        self.log_to_self("log metric", f"final score:\n{ round(scores['final_score'], 2) }")       


class MultiModalCleanUpScorer(GameScorer):
    def __init__(self, game_name: str, experiment: Dict, game_instance: Dict):
        super().__init__(game_name, experiment, game_instance)

    # def score_turns(self, episode_interactions: Dict) -> None:
    #     """ Turn-level scores """
    #     for turn_idx in range(len(episode_interactions)):
    #         for event in episode_interactions[turn_idx]:
    #             if event['type'] == 'player_response':
    #                 self.log_turn_score(turn_idx, 'response_received', 1)

    # def log_main_score(self, episode_interactions: Dict):
    #     if episode_interactions['success'] == 'true':
    #         self.log_episode_score("BENCH_SCORE", 100)
    #     elif episode_interactions['success'] == 'false':
    #         self.log_episode_score("BENCH_SCORE", 0)

    def compute_episode_scores(self, interactions: Dict):
        """Compute any game specific game episode scores/metrics e.g. an overall accuracy metric.

        Note: This method must log the game's main BENCH_SCORE

        Args:
            interactions: Dict containing the logged episode's interactions.
        """
        # self.log_episode_score("BENCH_SCORE", 0)
        print("===== in compute_episode_scores =====")
        # print(json.dumps(interactions, indent=4))
        # dummy implementation
        self.log_episode_score(BENCH_SCORE, interactions['final_score'])
        self.log_episode_score('distance_score', interactions['distance_score'])
        self.log_episode_score('consistency_score', interactions['consistency_score'])
        self.log_episode_score('coverage_score', interactions['coverage_score'])



class SomeGameBenchmark(GameBenchmark):

    def __init__(self, game_spec: GameSpec):
        super().__init__(game_spec)

    def create_game_master(self, experiment: Dict, player_models: List[Model]) -> GameMaster:
        return MultiModalCleanUpMaster(self.game_name, self.game_path, experiment, player_models)

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return MultiModalCleanUpScorer(self.game_name, experiment, game_instance)

