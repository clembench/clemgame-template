import os.path
from typing import Dict, Tuple, List, Union
import logging
import numpy as np

from clemcore.backends import Model
from clemcore.clemgame import GameSpec, GameMaster, GameBenchmark, Player, DialogueGameMaster, GameScorer, GameRecorder
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

        self.invalid_response = False

    def _does_game_proceed(self):
        """
        Proceed anyways. This should check for anything that ends an episode.
        """
        return True

    def _validate_player_response(self, player: Player, utterance: str) -> bool:
        if utterance:
            return True
        return False

    def compute_response_score(self, response, context):
        return 1 if self.is_success() else 0

    def compute_episode_score(self):
        if self.is_success():
            return 100 / (self.current_round + 1)  # zero-based
        return 0


class SomeGameScorer(GameScorer):
    def __init__(self, game_name: str, experiment: Dict, game_instance: Dict):
        super().__init__(game_name, experiment, game_instance)

    def compute_scores(self, episode_interactions: Dict) -> None:
        """ Episode level scores"""
        turn_scores = []
        prev_guess = None
        prev_guess_counter = 0
        prev_clue = None
        prev_clue_counter = 0
        invalid_response = False  # Note: This only takes into consideration that both players were compliant or not
        guesser_won = False
        for turn_idx, turn in enumerate(episode_interactions["turns"]):
            turn_score = {"guess": None, "clue": None, "request_count": 1}

            for event in turn:
                action = event["action"]
                if action["type"] == "invalid format":
                    invalid_response = True
                if action["type"] == "guess":
                    turn_score["guess"] = action["content"]
                if action["type"] == "clue":
                    turn_score["clue"] = action["content"]
                if action["type"] == "correct guess":
                    guesser_won = True

            if invalid_response:
                turn_score["violated_request_count"] = 1
                turn_score["parsed_request_count"] = 0
            else:
                turn_score["violated_request_count"] = 0
                turn_score["parsed_request_count"] = 1

            if turn_score["guess"] is not None and turn_score["guess"] == prev_guess:  # might be None, if clue is wrong
                prev_guess_counter += 1
            if turn_score["clue"] is not None and turn_score["clue"] == prev_clue:
                prev_clue_counter += 1
            self.log_turn_score(turn_idx, 'Accuracy', 1 if guesser_won else 0)
            self.log_turn_score(turn_idx, METRIC_REQUEST_COUNT_VIOLATED, turn_score["violated_request_count"])
            self.log_turn_score(turn_idx, METRIC_REQUEST_COUNT_PARSED, turn_score["parsed_request_count"])
            self.log_turn_score(turn_idx, METRIC_REQUEST_COUNT, turn_score["request_count"])
            prev_guess = turn_score["guess"]
            prev_clue = turn_score["clue"]
            turn_scores.append(turn_score)

        violated_request_count = sum([turn["violated_request_count"] for turn in turn_scores])
        self.log_episode_score(METRIC_REQUEST_COUNT_VIOLATED, violated_request_count)

        parsed_request_count = sum([turn["parsed_request_count"] for turn in turn_scores])
        self.log_episode_score(METRIC_REQUEST_COUNT_PARSED, parsed_request_count)

        request_count = sum([turn["request_count"] for turn in turn_scores])
        self.log_episode_score(METRIC_REQUEST_COUNT, request_count)

        self.log_episode_score(METRIC_REQUEST_SUCCESS, parsed_request_count / request_count)
        # checking the last guess (could be None) is ok,
        # b.c. the game ends only successfully, when there is a correct guess

        # Common metrics
        if invalid_response:  # whether a violation of the game rules happened (response not parsable)
            self.log_episode_score(METRIC_ABORTED, 1)
            self.log_episode_score(METRIC_SUCCESS, 0)
            self.log_episode_score(METRIC_LOSE, 0)
            # Game-specific metrics
            self.log_episode_score(BENCH_SCORE, np.nan)  # metric not applicable
        else:
            self.log_episode_score(METRIC_ABORTED, 0)
            if guesser_won:
                self.log_episode_score(METRIC_SUCCESS, 1)
                self.log_episode_score(METRIC_LOSE, 0)
                self.log_episode_score(BENCH_SCORE, 100 / len(turn_scores))  # how early the guesser found the word
            else:
                self.log_episode_score(METRIC_SUCCESS, 0)
                self.log_episode_score(METRIC_LOSE, 1)
                self.log_episode_score(BENCH_SCORE, 0)  # word not found

        # Game-specific metrics
        # How often the Guesser repeated a guess
        self.log_episode_score('Repetition-Guesser', prev_guess_counter)
        # How often the Describer repeated itself
        self.log_episode_score('Repetition-Describer', prev_clue_counter)
        # this might require a side-loop between describer and GM (game should not continue with Guesser)
        # self.log_episode_score('Rule-following', ...)


class SomeGameBenchmark(GameBenchmark):

    def __init__(self, game_spec: GameSpec):
        super().__init__(game_spec)
        # TODO: experiment could also be set through GameSpec

    def create_game_master(self, experiment: Dict, player_models: List[Model]) -> GameMaster:
        return SomeGameMaster(self.game_name, self.game_path, experiment, player_models)

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return SomeGameScorer(self.game_name, experiment, game_instance)

