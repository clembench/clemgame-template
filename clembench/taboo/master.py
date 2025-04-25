import os.path
from typing import Dict, Tuple, List, Union
import logging
import numpy as np

from clemcore.backends import Model
from clemcore.clemgame import GameSpec, GameMaster, GameBenchmark, Player, DialogueGameMaster, GameScorer
from clemcore.clemgame.master import ParseError, RuleViolationError, GameError
from clemcore.clemgame.metrics import METRIC_ABORTED, METRIC_SUCCESS, METRIC_LOSE, METRIC_REQUEST_COUNT, \
    METRIC_REQUEST_COUNT_VIOLATED, METRIC_REQUEST_COUNT_PARSED, METRIC_REQUEST_SUCCESS, BENCH_SCORE
from clemcore.utils import file_utils, string_utils

import nltk
from nltk.corpus import stopwords
from nltk.stem.snowball import SnowballStemmer

nltk.download('stopwords', quiet=True)
EN_STOPWORDS = stopwords.words('english')

EN_STEMMER = SnowballStemmer("english")

logger = logging.getLogger(__name__)

GUESS_PREFIX = "GUESS:"
CLUE_PREFIX = "CLUE:"


class WordGuesser(Player):

    def __init__(self, model: Model):
        super().__init__(model)
        self._custom_responses = ["Apple", "Banana", "Cherry"]

    def _custom_response(self, messages):
        word = self._custom_responses.pop(0)
        return f'{GUESS_PREFIX} {word}'


class WordDescriber(Player):

    def __init__(self, model: Model):
        super().__init__(model)
        self._custom_responses = ["(1) My first clue is ...", "(2) My second clue is ...", "(3) My third clue is ..."]

    def _custom_response(self, messages):
        clue = self._custom_responses.pop(0)
        return f"{CLUE_PREFIX} {clue}"


def check_clue(response: str, target_word: str, related_words: List[str], stemmer=EN_STEMMER):
    clue_words = string_utils.remove_punctuation(response).lower().split(" ")
    clue_words = [clue_word for clue_word in clue_words if clue_word not in EN_STOPWORDS]
    clue_word_stems = [stemmer.stem(clue_word) for clue_word in clue_words]
    target_word_stem = stemmer.stem(target_word)
    related_word_stems = [stemmer.stem(related_word) for related_word in related_words]

    for clue_word, clue_word_stem in zip(clue_words, clue_word_stems):  # raise first appearing exception
        if target_word_stem == clue_word_stem:
            reason = f"Target word '{target_word}' (stem={target_word_stem}) " \
                     f"is similar to clue word '{clue_word}' (stem={clue_word_stem})"
            raise RuleViolationError(reason, response)
        for related_word, related_word_stem in zip(related_words, related_word_stems):
            if related_word_stem == clue_word_stem:
                reason = f"Related word '{related_word}' (stem={related_word_stem}) " \
                         f"is similar to clue word '{clue_word}' (stem={clue_word_stem})"
                raise RuleViolationError(reason, response)


class Taboo(DialogueGameMaster):
    """
    This class implements a taboo game in which player A (the WordDescriber) is describing a
    target word that player B (the WordGuesser) needs to guess. Player A cannot use the target
    word or related words in their explanation. Morphology is checked in check_clue().
    """

    def __init__(self, game_name: str, game_path: str, experiment: Dict, player_models: List[Model]):
        super().__init__(game_name, game_path, experiment, player_models)
        self.max_rounds: int = experiment["max_turns"]

    def _on_setup(self, **game_instance):
        self.game_instance = game_instance

        self.target_word = game_instance["target_word"]
        self.related_words = game_instance["related_word"]

        describer_initial_prompt = self.experiment["describer_initial_prompt"]
        describer_initial_prompt = describer_initial_prompt.replace("$TARGET_WORD$", self.target_word)
        rel_words = f"- {self.related_words[0]}\n- {self.related_words[1]}\n- {self.related_words[2]}"
        describer_initial_prompt = describer_initial_prompt.replace("$REL_WORD$", rel_words)
        describer_initial_prompt = describer_initial_prompt.replace("$N$", str(self.max_rounds))

        guesser_initial_prompt = self.experiment["guesser_initial_prompt"]
        guesser_initial_prompt = guesser_initial_prompt.replace("$N$", str(self.max_rounds))

        self.describer = WordDescriber(self.player_models[0])
        self.guesser = WordGuesser(self.player_models[1])

        self.add_player(self.describer, initial_context=describer_initial_prompt)
        self.add_player(self.guesser, initial_prompt=guesser_initial_prompt)

        self.success, self.aborted, self.failure = False, False, False
        self.clue_error = None
        self.guess_word = None

    def _does_game_proceed(self):
        return not (self.aborted or self.failure or self.success)

    def _parse_response(self, player: Player, response: str) -> str:
        prefix = None
        if player == self.guesser:
            prefix = GUESS_PREFIX
        if player == self.describer:
            prefix = CLUE_PREFIX
        assert prefix is not None, f"Communication protocol not specified for player {player}"

        # validate communication protocol (this could also be done for each player individually)
        if not response.startswith(prefix):
            raise ParseError(f"response must start with {prefix}", response)
        self.log_to_self("valid response", "continue")

        # parse response content (here only remove the prefix)
        return response.replace(prefix, "").strip()

    def _on_parse_error(self, error: ParseError):
        self.log_to_self("invalid format", "abort game")
        self.aborted = True

    def _advance_game(self, player: Player, parsed_response: str):
        if player == self.describer:
            # validate game rules
            check_clue(parsed_response, self.target_word, self.related_words)  # throws RuleViolationError
            self.log_to_self("valid clue", parsed_response)
            # transition game state
            self.set_context_for(self.guesser, f"{CLUE_PREFIX} {self.guess_word}")
            
        if player == self.guesser:
            # validate game rules
            if len(parsed_response.split(" ")) > 0:
                raise RuleViolationError("guess has more than one word", parsed_response)
            self.log_to_self("valid guess", parsed_response)
            # transition game state
            self.guess_word = parsed_response[0]
            self.set_context_for(self.describer, f"{GUESS_PREFIX} {self.guess_word}")  # ignored if success

        # check game end conditions
        if self.guess_word.lower() == self.target_word:
            self.log_to_self("correct guess", "end game")
            self.success = True
        elif self.current_round == self.max_rounds - 1:  # zero-based
            raise RuleViolationError(f"max rounds ({self.max_rounds}) reached")

    def _on_game_error(self, error: GameError):
        # note: we could also introduce more concrete subclasses e.g. InvalidClueError and handle them here individually
        self.clue_error = error.reason
        self.log_to_self(self.clue_error, "failed game")
        self.failure = True

    def compute_turn_score(self):
        return 1 if self.success else 0

    def compute_episode_score(self):
        if self.success:
            return 100 / (self.current_round + 1)  # zero-based
        return 0


class TabooScorer(GameScorer):
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
                if action["type"] == "valid guess":
                    turn_score["guess"] = action["content"]
                if action["type"] == "valid clue":
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


class TabooGameBenchmark(GameBenchmark):

    def __init__(self, game_spec: GameSpec):
        super().__init__(game_spec)
        # TODO: experiment could also be set through GameSpec

    def create_game_master(self, experiment: Dict, player_models: List[Model]) -> GameMaster:
        return Taboo(self.game_name, self.game_path, experiment, player_models)

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return TabooScorer(self.game_name, experiment, game_instance)


def main():
    # select one experiment and instance
    game_path = os.path.dirname(os.path.abspath(__file__))
    experiments = file_utils.load_json("in/instances.json", game_path)
    experiment_1 = experiments["experiments"][0]
    game_1 = experiment_1["game_instances"][0]
    master = Taboo("taboo", experiment_1, ["mock", "mock"])
    master.setup(**game_1)
    master.play()


if __name__ == '__main__':
    main()
