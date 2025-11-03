from typing import Dict, Tuple, List, Union
import logging
import numpy as np

from clemcore.backends import Model
from clemcore.clemgame import GameSpec, GameBenchmark, GameMaster, Player, DialogueGameMaster, GameScorer, \
    GameError, ParseError, RuleViolationError
from clemcore.clemgame.metrics import METRIC_ABORTED, METRIC_SUCCESS, METRIC_LOSE, BENCH_SCORE

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
    def __init__(self, game_spec: GameSpec, experiment: Dict, player_models: List[Model]):
        super().__init__(game_spec, experiment, player_models)

    def _on_setup(self, **game_instance):
        self.game_instance = game_instance

        self.some_player = SomeGamePlayer(self.player_models[0])

        self.add_player(self.some_player, initial_context=game_instance['initial_prompt'])

        self.success = False

    def _advance_game(self, player: Player, parsed_response: str):
        if not parsed_response:
            raise RuleViolationError
        self.success = True
        self.log_to_self('player_response', parsed_response)

    def _parse_response(self, player: Player, response: str) -> str:
        if response:
            return response
        else:
            raise ParseError

    def _on_parse_error(self, error: GameError):
        self.success = False

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
            self.log_key(METRIC_SUCCESS, True)
        else:
            self.log_key(METRIC_SUCCESS, False)


class SomeGameScorer(GameScorer):
    def __init__(self, game_name: str, experiment: Dict, game_instance: Dict):
        super().__init__(game_name, experiment, game_instance)

    def compute_round_score(self, round_idx, round_events: List[Dict]) -> None:
        for event in round_events:
            if event["action"]["type"] == "player_response":
                self.log_round_score(round_idx,'response_received', 1)

    def compute_episode_scores(self, interactions: Dict):
        if interactions[METRIC_SUCCESS]:
            self.log_episode_score(BENCH_SCORE, 100)
        elif interactions[METRIC_LOSE]:
            self.log_episode_score(BENCH_SCORE, 0)
        elif interactions[METRIC_ABORTED]:
            self.log_episode_score(BENCH_SCORE, np.nan)
        else:
            raise ValueError("Missing outcome value (success, failure, abort) in interactions.json")


class SomeGameBenchmark(GameBenchmark):

    def __init__(self, game_spec: GameSpec):
        super().__init__(game_spec)

    def create_game_master(self, experiment: Dict, player_models: List[Model]) -> GameMaster:
        return SomeGameMaster(self.game_spec, self.game_path, experiment, player_models)

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return SomeGameScorer(self.game_name, experiment, game_instance)