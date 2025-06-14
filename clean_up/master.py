import os.path
from typing import Dict, Tuple, List, Union
import logging
import numpy as np
from string import Template
import re

from clemcore.backends import Model
from clemcore.clemgame import GameSpec, GameMaster, GameBenchmark, Player, DialogueGameMaster, GameScorer, \
    GameError, ParseError, RuleViolationError
from clemcore.clemgame.metrics import METRIC_ABORTED, METRIC_SUCCESS, BENCH_SCORE, METRIC_LOSE # METRIC_REQUEST_COUNT, \
    # METRIC_REQUEST_COUNT_VIOLATED, METRIC_REQUEST_COUNT_PARSED, METRIC_REQUEST_SUCCESS, BENCH_SCORE
from clemcore.utils import file_utils, string_utils
from resources.grids.game_grid import GameGrid, DISTANCE_SCORE, TOTAL_DISTANCE

logger = logging.getLogger(__name__)


class Cleaner(Player):
    def __init__(self, model: Model):
        super().__init__(model)
        self._custom_responses = ["move(C,1,1)", "say(Let's move C to the top left corner.)"] # , "say(Move C to (1, 1).)",]
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

    def _on_setup(self, **game_instance):
        self.game_instance = game_instance

        self.player_1 = Cleaner(self.player_models[0])
        self.player_1.grid = GameGrid(self.game_instance['background'])
        self.player_1.grid.set_objects(self.game_instance['state1'])
        self.player_1.grid.show_coords = self.game_instance['show_coords']
        self.player_2 = Cleaner(self.player_models[1])
        self.player_2.grid = GameGrid(self.game_instance['background'])
        self.player_2.grid.set_objects(self.game_instance['state2'])
        self.player_2.grid.show_coords = self.game_instance['show_coords']

        self.add_player(self.player_1, initial_context=self.game_instance['p1_initial_prompt'])
        self.add_player(self.player_2)

        self.finished = False   # This is for negotiating the end of the game using `terminate_question` and `terminate_answer`
        self.success = False    # True if game finished regularly
        self.terminate = False  # True if game is terminated because of rule violation or parse error
        self.aborted = False  # True if game is aborted due to a rule violation or parse error
        self.penalties = 0      # Number of collectively accumulated penalties
        self.max_penalties = self.game_instance['max_penalties']    # For strict mode, max_penalties is 0
        self.pass_turn = True
        self.max_rounds = self.game_instance['max_rounds']

    def _other_player(self) -> Player:
        """
        Returns the player who will be next.
        """
        other_player_idx = (self._current_player_idx + 1) % len(self.players_by_names)
        return self.get_players()[other_player_idx]

    def _parse_response(self, player: Player, response: str) -> str:
        self.log_to_self('player_response', response)
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
                elif response == self.game_instance['terminate_answer'] and self.finished:
                    self.success = True
                    self.terminate = True
                    self.log_to_self('success', 'true')
                else:
                    for restricted in self.game_instance['restricted']:
                        match = re.compile(restricted).search(response)
                        if match:
                            self.terminate = True
                            self.aborted = True
                            self.log_to_self('rule_violation', f"Response violates restriction: {restricted}")
                            logger.warning(f"Response '{response}' violates restriction: {restricted}")
                return response
            else:
                self.terminate = True
                self.aborted = True
                self.log_to_self('parse_error', f"Invalid response format")
                raise ParseError(f"Invalid response format: {response}")

    # def _on_parse_error(self, error: GameError):
    #     self.success = False

    def _should_pass_turn(self) -> bool:
        """
        Check if the player should pass their turn.
        """
        return self.pass_turn         

    def _advance_game(self, player: Player, parsed_response: str):
        # logger.info(f"Messages for {player.name}:\n")
        # for message in player.messages:
        #     logger.info(f"  {message}")
        if not parsed_response:
            raise RuleViolationError
        # self.success = True
        match = re.compile(self.game_instance['move_pattern']).match(parsed_response)
        if match:
            obj = match.group('obj')
            x = int(match.group('x'))
            y = int(match.group('y'))
            success, message = player.grid.move_abs(obj, x, y, check_empty=True)
            self.pass_turn = success
            self.set_context_for(player, message)
            if success:
                # log the move message to the player and add it to the message history (without response)
                self.log_to_self('valid move', message)
                self.log_event(from_="GM", to=player.name, action={'type': "send message", 'content': message })
                player._messages.append(dict(role='user', content=message))
                # turn is passed to the other player
                next_player_prompt = self._penalty_counter_message()
                next_player_prompt += self.game_instance["new_turn_move"]
                self.set_context_for(self._other_player(), next_player_prompt)
            if not success:
                # Player is reprompted with a penalty, their turn continues. 
                self.penalties += 1
                message = message + "\n" + Template(self.game_instance['move_penalty']).substitute(penalty=self.penalties, max_penalties=self.max_penalties)
                self.log_to_self('invalid move', message)
                self.set_context_for(player, message)
                # raise RuleViolationError(f"Invalid move: {message}")
        else:
            match = re.compile(self.game_instance['message_pattern']).match(parsed_response)
            if match:
                self.pass_turn = True
                message = match.group('message')
                # logger.info(f"Player {player.name} said: {message}")
                if self.current_round == 0 and player == self.player_1:
                    initial_prompt_p2 = Template(self.game_instance['p2_initial_prompt']).substitute(
                        start_message=message
                    )
                    # logger.info(f'Initial prompt for player 2: {initial_prompt_p2}')
                    self.set_context_for(self.player_2, initial_prompt_p2)
                else:
                    # logger.info(f"Setting context for player {self._next_player().name} with new turn message: {Template(self.game_instance['new_turn']).substitute(turn_message=message)}.")
                    next_player_prompt = self._penalty_counter_message()
                    next_player_prompt += Template(self.game_instance['new_turn']).substitute(turn_message=message)
                    self.set_context_for(self._other_player(), next_player_prompt)
            else:
                raise ParseError(f"Invalid response format: {parsed_response}")
            
    def _penalty_counter_message(self) -> str:
        """
        Returns a message with the current penalty count.
        """
        if self.max_penalties > 0:
            return Template(self.game_instance['penalty_counter']).substitute(
                penalty=self.penalties, max_penalties=self.max_penalties
            )
        # In case of strict mode (self.max_penalties == 0), we return and empty string
        return ""

    def _does_game_proceed(self):
        """
        Proceed anyways. This should check for anything that ends an episode.
        """
        if self.penalties > self.max_penalties:
            self.log_to_self('end', 'Maximum number of penalties exceeded')
            return False
        if self.terminate:
            return False
        if self.current_round >= self.max_rounds:  # Arbitrary limit for rounds
            logger.info("Maximum number of rounds reached, ending game.")
            self.log_to_self('end', 'Maximum number of rounds reached')
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
        grid_scores = self.player_1.grid.get_scores(self.player_2.grid)
        for key, value in grid_scores.items():
            self.log_key(key, value)
        self.log_key('Penalties', self.penalties)
        self.log_key('Object Count', len(self.player_1.grid.objects))
        self.log_key(METRIC_ABORTED, int(self.aborted))
        self.log_key(METRIC_SUCCESS, int(self.success))
        self.log_key(METRIC_LOSE, int(not self.success))

class CleanUpScorer(GameScorer):
    def __init__(self, game_name: str, experiment: Dict, game_instance: Dict):
        super().__init__(game_name, experiment, game_instance)

    def score_turns(self, episode_interactions: Dict) -> None:
        """ Turn-level scores """
        for turn_idx in range(len(episode_interactions)):
            for event in episode_interactions[turn_idx]:
                if event['type'] == 'player_response':
                    self.log_turn_score(turn_idx, 'response_received', 1)

    def compute_episode_scores(self, episode_interactions: Dict) -> float:
        """ Compute the episode score based on the interactions """
        turn_count = len(episode_interactions['turns'])
        penalties = episode_interactions['Penalties']
        obj_count = episode_interactions['Object Count']

        self.log_episode_score("Penalties", penalties)
        self.log_episode_score("Turn Count", turn_count)

        total_distance = episode_interactions[TOTAL_DISTANCE]
        self.log_episode_score(TOTAL_DISTANCE, total_distance)
        distance_score = episode_interactions[DISTANCE_SCORE]
        self.log_episode_score(DISTANCE_SCORE, distance_score)
        # we allow two turns per object, after that every turn adds a penalty
        turn_count = max(turn_count - obj_count * 2, 0)
        penalties += turn_count
        if penalties > 0:
            penalty_score = 1 / penalties
        else:
            penalty_score = 1
        self.log_episode_score("Penalty Score", penalty_score)
        # The final score is a product of the distance score and the penalty score
        logger.info(f"Game: {episode_interactions['meta']['game_name']}, experiment: {episode_interactions['meta']['experiment_name']}, game_id: {episode_interactions['meta']['game_id']}, dialogue_pair: {episode_interactions['meta']['dialogue_pair']}")
        logger.info(f'{METRIC_SUCCESS}: {episode_interactions[METRIC_SUCCESS]}, {METRIC_ABORTED}: {episode_interactions[METRIC_ABORTED]}')
        if episode_interactions[METRIC_SUCCESS]:
            logger.info(f'success, logging Main Score as {distance_score * penalty_score}')
            self.log_episode_score(BENCH_SCORE, distance_score * penalty_score)
        elif episode_interactions[METRIC_ABORTED]:
            logger.info(f'aborted, logging Main Score as np.nan')
            self.log_episode_score(BENCH_SCORE, np.nan)
    # def log_main_score(self, episode_interactions: Dict):
    #     if episode_interactions['success'] == 'true':
    #         self.log_episode_score("BENCH_SCORE", 100)
    #     elif episode_interactions['success'] == 'false':
    #         self.log_episode_score("BENCH_SCORE", 0)


class SomeGameBenchmark(GameBenchmark):

    def __init__(self, game_spec: GameSpec):
        super().__init__(game_spec)

    def create_game_master(self, experiment: Dict, player_models: List[Model]) -> GameMaster:
        return CleanUpMaster(self.game_name, self.game_path, experiment, player_models)

    def create_game_scorer(self, experiment: Dict, game_instance: Dict) -> GameScorer:
        return CleanUpScorer(self.game_name, experiment, game_instance)

