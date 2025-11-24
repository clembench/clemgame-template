from typing import Dict

from clemcore.backends import CustomResponseModel
from clemcore.clemgame import GameSpec, GameInstanceIterator, DialogueGameMaster
from gymnasium import spaces
from pettingzoo import AECEnv
from pettingzoo.utils.env import AgentID, ObsType, ActionType

from clembench.taboo.master import Taboo


def env():
    # Look for the packaged clemgame json
    # NOTE: This feels a bit weird, because we don't need a path anymore, when we make this installable;
    # and all the other values are rather documentary.
    game_spec = GameSpec.from_directory(".")[0]
    # Load the packaged default instances.json to be played
    game_iterator = GameInstanceIterator.from_game_spec(game_spec).reset()
    # Load the instance data
    experiment, game_instance = next(game_iterator)
    # Load the game and pre-set the default instance
    # todo: experiment must be set during reset or set during env creation (which is a bit weird)!
    game = Taboo(game_spec, experiment, [CustomResponseModel(), CustomResponseModel()])
    # Wrap everything in a pettingzoo style env
    return PettingZooEnv(game, game_instance)


class PettingZooEnv(AECEnv):

    def __init__(self, game_master: DialogueGameMaster, default_game_instance: Dict):
        super().__init__()
        self.game_master = game_master
        self.default_game_instance = default_game_instance

        # initialize pettingzoo env
        self.metadata = dict(name=game_master.game_spec.game_name)
        self.observation_spaces = dict()
        self.action_spaces = dict()
        self.rewards = dict()
        self.terminations = dict()
        self.truncations = dict()
        self._cumulative_rewards = dict()
        self.infos = dict()
        self.agents = []
        self.possible_agents = []

    def reset(
            self,
            seed: int | None = None,
            options: dict | None = None,
    ) -> None:
        self.game_master.setup(**self.default_game_instance)
        # Only after setup() the players are set (which is a bit weird)
        self.agents = self.game_master.get_players()
        self.possible_agents = self.agents
        self.agent_selection = self.game_master.current_player

        for player in self.game_master.get_players():
            # GameMaster should implement this by default;
            # OK maybe the the implemented game should provide a more concrete upper bound on the content length
            # If you have images, then you should also define them here
            self.observation_spaces[player] = spaces.Dict(
                {
                    "role": spaces.Text(max_length=128),  # should be enough chars for a role name
                    "content": spaces.Text(max_length=8192)  # should be enough chars for prompt and context
                }
            )
            # the Players should become the action space (I guess)
            self.action_spaces[player] = player
            self.terminations[player] = False
            self.truncations[player] = False
            self.rewards[player] = 0.
            self._cumulative_rewards[player] = 0.
            self.infos[player] = {}

    def step(self, action: ActionType) -> None:
        """Accepts and executes the action of the current agent_selection in the environment.

        Automatically switches control to the next agent.
        """
        # after step current_player might have changed, so we reference it here already
        # current_player should move into GameMaster
        current_player = self.game_master.current_player
        done, info = self.game_master.step(action)
        # for now we only have the case that all players end at the same time
        for player in self.game_master.get_players():
            self.terminations[player] = done
            self.truncations[player] = done
        self.infos[current_player] = info
        self.rewards[current_player] = info["turn_score"]
        self._accumulate_rewards()
        if done:
            self.agent_selection = None
            self.agents = []  # this signals the play loop to terminate
        # next player
        self.agent_selection = self.game_master.current_player

    def observe(self, agent: AgentID) -> ObsType | None:
        """Returns the observation an agent currently can make.

        `last()` calls this function.
        """
        return self.game_master.get_context_for(agent)
