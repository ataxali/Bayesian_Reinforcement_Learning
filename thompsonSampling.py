import numpy as np

class HistoryManager(object):
    def __init__(self, actions):
        self.history = list()
        self.action_count_dict = dict.fromkeys(actions, 0)

    def get_history(self):
        return self.history

    def get_action_count_dict(self):
        return self.action_set

    def add(self, observation):
        # each observation must be <orig_state, action, reward, new_state>
        if not isinstance(observation, tuple):
            observation = tuple(observation)
        if not len(observation) == 4:
            raise Exception("<orig_state, action, reward, new_state>")
        self.history.append(observation)
        if observation[1] in self.action_count_dict:
            self.action_count_dict[observation[1]] += 1
        else:
            raise Exception(str(observation[1]),
                            " does not exist in action set dictionary")


class ThompsonSampler(object):
    def __init__(self, history_manager, branching_factor):
        self.history_manager = history_manager
        self.branching_factor = branching_factor

    def get_action_set(self):
        action_psuedo_counts = self.history_manager.get_action_set()
        actions = action_psuedo_counts.keys()
        alphas = action_psuedo_counts.values()
        action_probs = np.random.dirichlet(alphas, 1)
        unif_samples = np.random.uniform(size=self.branching_factor)
        action_set = set()
        for sample in unif_samples:
            for prob_i in range(len(action_probs)):
                if sample < action_probs[prob_i]:
                    action_set.add(actions[prob_i])