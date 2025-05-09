import os.path
from typing import Dict, Tuple, List, Union
import logging
import numpy as np

from clemcore.backends import Model
from clemcore.clemgame import GameSpec, GameMaster, GameBenchmark, Player, DialogueGameMaster, GameScorer, \
    GameError, ParseError, RuleViolationError
from clemcore.clemgame.metrics import METRIC_ABORTED, METRIC_SUCCESS, METRIC_LOSE, METRIC_REQUEST_COUNT, \
    METRIC_REQUEST_COUNT_VIOLATED, METRIC_REQUEST_COUNT_PARSED, METRIC_REQUEST_SUCCESS, BENCH_SCORE
from clemcore.utils import file_utils, string_utils

logger = logging.getLogger(__name__)


class SomeGamePlayer(Player):
    def __init__(self, model: Model):
        super().__init__(model)
        self._custom_responses = ["Apple", "Banana", "Cherry"]

    def _custom_response(self, messages):
        word = self._custom_responses.pop(0)
        return f'{word}'


class SomeGameMaster(DialogueGameMaster):
    """
    Template class for game master.
    """
    def __init__(self, game_name: str, game_path: str, experiment: Dict, player_models: List[Model]):
        super().__init__(game_name, game_path, experiment, player_models)

    def _on_setup(self, **game_instance):
        self.game_instance = game_instance

        self.some_player = SomeGamePlayer(self.player_models[0])

        self.add_player(self.some_player, initial_context=game_instance['initial_prompt'])

        self.success = False

    def _parse_response(self, player: Player, response: str) -> str:
        if response:
            return response
        else:
            raise ParseError

    def _on_parse_error(self, error: GameError):
        self.success = False

    def _advance_game(self, player: Player, parsed_response: str):
        if not parsed_response:
            raise RuleViolationError
        self.success = True
        self.log_to_self('player_response', parsed_response)

    def _does_game_proceed(self):
        """
        Proceed anyways. This should check for anything that ends an episode.
        """
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
        return SomeGameMaster(self.game_name, self.game_path, experiment, player_models)

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return SomeGameScorer(self.game_name, experiment, game_instance)

