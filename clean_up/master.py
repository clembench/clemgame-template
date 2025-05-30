import os.path
from typing import Dict, Tuple, List, Union
import logging
import numpy as np
from string import Template
import re

from clemcore.backends import Model
from clemcore.clemgame import GameSpec, GameMaster, GameBenchmark, Player, DialogueGameMaster, GameScorer, \
    GameError, ParseError, RuleViolationError
# from clemcore.clemgame.metrics import METRIC_ABORTED, METRIC_SUCCESS, METRIC_LOSE, METRIC_REQUEST_COUNT, \
#     METRIC_REQUEST_COUNT_VIOLATED, METRIC_REQUEST_COUNT_PARSED, METRIC_REQUEST_SUCCESS, BENCH_SCORE
from clemcore.utils import file_utils, string_utils
from resources.grids.game_grid import GameGrid

logger = logging.getLogger(__name__)


class Cleaner(Player):
    def __init__(self, model: Model):
        super().__init__(model)
        self._custom_responses = ["move(C,1,1)", "say(Let's move C to the top left corner.)"]
        self.grid = None  # This will be set in the game master

    def _custom_response(self, messages):
        response = self._custom_responses[np.random.randint(0, len(self._custom_responses))]
        return response

class CleanUpMaster(DialogueGameMaster):
    """
    Template class for game master.
    """
    def __init__(self, game_name: str, game_path: str, experiment: Dict, player_models: List[Model]):
        super().__init__(game_name, game_path, experiment, player_models)
        self.terminate = False

    def _on_setup(self, **game_instance):
        self.game_instance = game_instance

        self.player_1 = Cleaner(self.player_models[0])
        self.player_1.grid = GameGrid(self.game_instance['grid1'])
        self.player_1.grid.set_objects(self.game_instance['objects1'])
        self.player_2 = Cleaner(self.player_models[1])
        self.player_2.grid = GameGrid(self.game_instance['grid2'])
        self.player_2.grid.set_objects(self.game_instance['objects2'])

        initial_prompt_p1 = Template(self.game_instance['initial_prompt']).substitute(
            grid=str(self.player_1.grid), 
            objects=self.player_1.grid.object_string(), 
            max_x=self.game_instance['width']-1, 
            max_y=self.game_instance['height']-1, 
            empty_symbol=self.game_instance['empty_symbol'],
            max_penalties=self.game_instance['max_penalties'],
            start_message=self.game_instance['p1_start']
            )
        # logger.info(f'Initial prompt for player 1: {initial_prompt_p1}')
        self.add_player(self.player_1, initial_context=initial_prompt_p1)
        self.add_player(self.player_2)

        self.finished = False
        self.success = False
        self.penalties = 0
        self.pass_turn = True

    def _other_player(self) -> Player:
        """
        Returns the player who will be next.
        """
        other_player_idx = (self._current_player_idx + 1) % len(self.players_by_names)
        return self.get_players()[other_player_idx]

    def _parse_response(self, player: Player, response: str) -> str:
        # logger.info(f"Parsing response of player {player.name}, current round: {self.current_round}")
        # TODO: for now, we will just remove backticks and newlines
        response = response.replace('`', '').replace('\n', ' ').strip()
        match = re.compile(self.game_instance['move_pattern']).match(response)
        if match:
            return response
        else:
            match = re.compile(self.game_instance['message_pattern']).match(response)
            if match:
                if response == self.game_instance['terminate_question']:
                    self.finished = True
                if response == self.game_instance['terminate_answer'] and self.finished:
                    self.success = True
                    self.terminate = True
                    self.log_to_self('success', 'true')
                return response
            else:
                self.terminate = True
                raise ParseError(f"Invalid response format: {response}")

    def _on_parse_error(self, error: GameError):
        self.success = False

    def _should_pass_turn(self) -> bool:
        """
        Check if the player should pass their turn.
        """
        return self.pass_turn         

    def _advance_game(self, player: Player, parsed_response: str):
        logger.info(f"Messages for {player.name}:\n")
        for message in player.messages:
            logger.info(f"  {message}")
        if not parsed_response:
            raise RuleViolationError
        # self.success = True
        self.log_to_self('player_response', parsed_response)
        match = re.compile(self.game_instance['move_pattern']).match(parsed_response)
        if match:
            obj = match.group('obj')
            x = int(match.group('x'))
            y = int(match.group('y'))
            success, message = player.grid.move_abs(obj, x, y, check_empty=True)
            self.pass_turn = success
            self.set_context_for(player, message)
            if success:
                self.log_to_self('valid move', message)
                # self.set_context_for(player, message)
                # player.add_next_message(message)
                self.log_event(from_="GM", to=player.name, action={'type': "send message", 'content': message })
                player._messages.append(dict(role='user', content=message))
                logger.info("Valid move by player %s: %s", player.name, message)
                self.set_context_for(self._other_player(), self.game_instance["new_turn_move"])
            if not success:
                # self.terminate = True
                self.penalties += 1
                message = message + "\n" + Template(self.game_instance['penalty']).substitute(penalty=self.penalties, max_penalties=self.game_instance['max_penalties'])
                self.log_to_self('invalid move', message)
                self.set_context_for(player, message)
                # raise RuleViolationError(f"Invalid move: {message}")
            self.set_context_for(self._other_player(), self.game_instance["new_turn_move"])
        else:
            match = re.compile(self.game_instance['message_pattern']).match(parsed_response)
            if match:
                self.pass_turn = True
                message = match.group('message')
                # logger.info(f"Player {player.name} said: {message}")
                if self.current_round == 0 and player == self.player_1:
                    initial_prompt_p2 = Template(self.game_instance['initial_prompt']).substitute(
                        grid=str(self.player_2.grid), 
                        objects=self.player_2.grid.object_string(), 
                        max_x=self.game_instance['width']-1, 
                        max_y=self.game_instance['height']-1, 
                        empty_symbol=self.game_instance['empty_symbol'],
                        max_penalties=self.game_instance['max_penalties'],
                        start_message=Template(self.game_instance['p2_start']).substitute(start_message=message)
                    )
                    # logger.info(f'Initial prompt for player 2: {initial_prompt_p2}')
                    self.set_context_for(self.player_2, initial_prompt_p2)
                else:
                    # logger.info(f"Setting context for player {self._next_player().name} with new turn message: {Template(self.game_instance['new_turn']).substitute(turn_message=message)}.")
                    self.set_context_for(self._other_player(), Template(self.game_instance["new_turn"]).substitute(turn_message=message))
            else:
                raise ParseError(f"Invalid response format: {parsed_response}")

    def _does_game_proceed(self):
        """
        Proceed anyways. This should check for anything that ends an episode.
        """
        if self.terminate:
            return False
        if self.current_round >= 20:  # Arbitrary limit for rounds
            logger.info("Maximum number of rounds reached, ending game.")
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
        return CleanUpMaster(self.game_name, self.game_path, experiment, player_models)

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return SomeGameScorer(self.game_name, experiment, game_instance)

