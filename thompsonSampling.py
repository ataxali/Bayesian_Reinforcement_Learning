import numpy as np

class HistoryManager(object):
    def __init__(self, actions):
        self.history = list()
        self.action_count_reward_dict = dict.fromkeys(actions, (0, 0))
        self.total_rewards = 0

    def get_history(self):
        return self.history

    def get_action_count_reward_dict(self):
        return self.action_count_reward_dict

    def get_total_rewards(self):
        return self.total_rewards

    def add(self, observation):
        # each observation must be <orig_state, action, reward, new_state>
        if not isinstance(observation, tuple):
            observation = tuple(observation)
        if not len(observation) == 4:
            raise Exception("<orig_state, action, reward, new_state>")
        self.history.append(observation)
        if observation[1] in self.action_count_reward_dict:
            count, reward = self.action_count_reward_dict[observation[1]]
            self.action_count_reward_dict[observation[1]] = (count+1, reward+observation[2])
            self.total_rewards += observation[2]
        else:
            raise Exception(str(observation[1]),
                            " does not exist in action set dictionary")


class ThompsonSampler(object):
    def __init__(self, history_manager, branching_factor):
        self.history_manager = history_manager
        self.branching_factor = branching_factor

    def get_action_set(self, scale_by_rewards = True):
        action_psuedo_counts = self.history_manager.get_action_count_reward_dict()
        actions = action_psuedo_counts.keys()
        alphas = map(lambda x: x[0], action_psuedo_counts.values())
        action_probs = np.random.dirichlet(list(alphas), 1)
        if not scale_by_rewards:
            return self.__reduce_action_space(action_probs=np.cumsum(action_probs),
                                              actions=actions)
        else:
            rewards = map(lambda x: x[1]/float(self.history_manager.get_total_rewards()),
                          action_psuedo_counts.values())
            action_probs = [prob*reward for (prob, reward) in zip(action_probs, rewards)]
            action_probs = np.cumsum(action_probs)
            return self.__reduce_action_space(action_probs=action_probs,
                                              actions=actions)

    def __reduce_action_space(self, action_probs, actions):
        return np.random.choice(list(actions), self.branching_factor,
                      p=action_probs/sum(action_probs), replace=False)
    