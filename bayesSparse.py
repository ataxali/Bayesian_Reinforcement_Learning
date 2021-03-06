# Pseudocode
#
# GrowSparseTree (node, branchfactor, horizon)
#     If node.depth = horizon; return
#     If node.type = “decision”
#     For each a ∈ A
#         child = (“outcome”, depth, node.belstate, a)
#         GrowSparseTree (child, branchfactor, horizon)
#     If node.type = “outcome”
#         For i = 1...branchfactor
#         [rew,obs] = sample(node.belstate, node.act)
#         post = posterior(node.belstate, obs)
#         child = (“decision”, depth+1, post, [rew,obs])
#         GrowSparseTree (child, branchfactor, horizon)
#
# EvaluateSubTree (node, horizon)
#     If node.children = empty
#         immed = MaxExpectedValue(node.belstate)
#         return immed * (horizon - node.depth)
#     If node.type = “decision”
#         return max(EvaluateSubTree(node.children))
#     If node.type = “outcome”
#         values = EvaluateSubTree(node.children)
#         return avg(node.rewards + values)

import enum
import numpy as np
from global_constants import print_debug
from mdpSimulator import MDPSimulator


NodeType = enum.Enum("NodeType", "Outcome Decision")


class SparseTree(object):

    class Node(object):
        def __init__(self, type, depth, state, value):
            self.type = type
            self.depth = depth
            self.state = state
            self.value = value

        def __str__(self):
            return "[" + str(self.type) + ":" + str(self.depth) + ":" + str(self.value) + "]"

    def __init__(self, node, parent, actions=None):
        self.node = node
        self.parent = parent
        self.actions = actions
        self.children = []

    def add_child(self, child):
        self.children.append(child)

    def append_val_to_parent(self, value):
        self.parent.node.value.append(value)

    def __str__(self):
        children_str = "{"
        for child in self.children:
            children_str += " " + str(child.node)
        children_str += "}"
        return str(self.node) + " -> " + children_str

    def get_tree_size(self):
        if not self.children and self.node.type == NodeType.Decision:
            return 1
        if not self.children:
            return 0
        return 1 + sum(map(lambda child: child.get_tree_size(), self.children))

    def get_tree_depth(self):
        if len(self.children) == 0:
            return self.node.depth
        return max(map(lambda child: child.get_tree_depth(), self.children))


class SparseTreeEvaluator(object):

        def __init__(self, mdp_simulator, root_state, action_set, horizon,
                     history_manager, state_posterior, goal_state, goal_reward,
                     loss_penalty, thompson_sampler=None,
                     discount_factor=0.05):
            self.simulator = mdp_simulator
            self.root_state = root_state
            self.action_set = action_set
            self.horizon = horizon
            self.lookahead_tree = None
            self.thompson_sampler = thompson_sampler
            self.discount_factor = discount_factor
            self.history_manager = history_manager
            self.state_posterior = state_posterior
            self.goal_state = goal_state
            self.loss_penalty = loss_penalty
            self.goal_reward = goal_reward
            self.ignored_specials = []

        def evaluate(self, t):
            root_node = SparseTree.Node(NodeType.Decision, 0, self.root_state, [])
            lookahead_tree = SparseTree(root_node, None)
            specials = []
            for i in range(-1, self.horizon+2):
                specials_t = []
                self.__predict_specials(specials_t, t + i)
                specials.append(set(specials_t))
            self.__grow_sparse_tree(lookahead_tree, specials)
            self.__eval_sparse_tree(lookahead_tree, specials)
            self.lookahead_tree = lookahead_tree

        def __str__(self):
            children_str = "{"
            for child in self.lookahead_tree.children:
                children_str += " " + str(child.node)
            children_str += "}"
            return str(self.lookahead_tree.node) + " -> " + children_str

        def __predict_specials(self, specials, time):
            x_preds, y_preds = self.state_posterior.predict(time)
            for x in x_preds[0]:
                for y in y_preds[0]:
                    specials.append((int(round(x[0])), int(round(y[0])), "red", self.loss_penalty, "NA"))

        def __grow_sparse_tree(self, lookahead_tree, specials):
            if (lookahead_tree.node.depth >= self.horizon) and (lookahead_tree.node.type == NodeType.Decision):
                # leaves of sparse tree should be outcome nodes
                return

            if lookahead_tree.node.type == NodeType.Decision:
                specials_t = list(set(specials[lookahead_tree.node.depth]) |
                                  set(specials[lookahead_tree.node.depth + 1]) |
                                  set(specials[lookahead_tree.node.depth + 2]))
                specials_t.append((
                                    self.goal_state[0], self.goal_state[1], "green",
                                self.goal_reward, "NA"))
                statics = self.state_posterior.get_static_states()
                # if we are at root node, and asked to evaluate decision tree
                # we assume that special and tree root cannot overlap
                # otherwise, there is no tree to construct
                filtered_specials = specials_t.copy()
                if lookahead_tree.node.depth == 0:
                    for idx, (i, j, c, r, v) in enumerate(specials_t):
                        if lookahead_tree.node.state[0] == i and lookahead_tree.node.state[1] == j:
                            print("Root at special", (i, j, c, r, v))
                            if not c == "green":
                                self.ignored_specials.append([i, j])
                                filtered_specials.pop(idx)
                if lookahead_tree.node.depth == 0 and self.thompson_sampler:
                    move_pool = self.__get_actions(lookahead_tree, filtered_specials, statics, True)
                    lookahead_tree.actions = move_pool
                else:
                    move_pool = self.__get_actions(lookahead_tree, filtered_specials, statics, False)
                    lookahead_tree.actions = move_pool
                for action in move_pool:
                    orig_state, child_action, child_reward, child_state, _ = \
                        self.simulator.sim(lookahead_tree.node.state, action,
                                           specials=filtered_specials, walls=statics)
                    if list(child_state) == list(orig_state):
                        continue
                    child = SparseTree(SparseTree.Node(NodeType.Outcome, lookahead_tree.node.depth,
                                                       child_state, [child_reward]), lookahead_tree)
                    lookahead_tree.add_child(child)
                    if print_debug: print("Added outcome child depth",  child)
                    self.__grow_sparse_tree(child, specials)

            if lookahead_tree.node.type == NodeType.Outcome:
                child = SparseTree(SparseTree.Node(NodeType.Decision,
                                                   lookahead_tree.node.depth + 1,
                                                   lookahead_tree.node.state, []), lookahead_tree)
                lookahead_tree.add_child(child)
                self.__grow_sparse_tree(child, specials)

        def __eval_sparse_tree(self, lookahead_tree, t):
            for child in lookahead_tree.children:
                self.__eval_sparse_tree(child, t)

            if lookahead_tree.node.type == NodeType.Outcome:
                state_reward = lookahead_tree.node.value.pop(0)
                if lookahead_tree.node.value:
                    reward_avg = state_reward + (sum(lookahead_tree.node.value) / float(len(lookahead_tree.node.value)))
                else:
                    reward_avg = state_reward
                if len(lookahead_tree.children) == 0:
                    depth_factor = max(self.horizon, lookahead_tree.node.depth) - lookahead_tree.node.depth + 1
                    lookahead_tree.append_val_to_parent(reward_avg * float(depth_factor) * self.discount_factor)
                else:
                    # average present and future rewards
                    lookahead_tree.append_val_to_parent(reward_avg * self.discount_factor)

            if lookahead_tree.node.type == NodeType.Decision:
                if lookahead_tree.node.depth == 0:
                    # set sparse tree root value to
                    # (best_action_index, max_avg_reward_value_discounted)
                    if len(lookahead_tree.node.value) == 0:
                        print(lookahead_tree.node.state)
                        print(lookahead_tree.actions)
                        print(lookahead_tree.node)
                    max_value = max(lookahead_tree.node.value)
                    max_idxs = [i for i, j in enumerate(lookahead_tree.node.value) if j == max_value]
                    lookahead_tree.node.value = (max_idxs, max_value, [lookahead_tree.node.value])
                else:
                    # maximize the averages and discount the max
                    if len(lookahead_tree.node.value):
                        present_reward = max(lookahead_tree.node.value)
                        if len(lookahead_tree.children) == 0:
                            depth_factor = max(self.horizon,
                                               lookahead_tree.node.depth) - lookahead_tree.node.depth + 1
                            lookahead_tree.append_val_to_parent(present_reward *
                                                                float(depth_factor))
                        else:
                            lookahead_tree.append_val_to_parent(present_reward)

        def __get_actions(self, root, specials, statics, use_tsampler):
            if use_tsampler:
                valid_actions = self.simulator.get_valid_actions(root.node.state,
                                                                 self.action_set,
                                                                 specials=specials,
                                                                 walls=statics)
                return self.thompson_sampler.get_action_set(valid_actions)
            else:
                return self.simulator.get_valid_actions(root.node.state,
                                                                 self.action_set,
                                                                 specials=specials,
                                                                 walls=statics)

        def __get_states(self, root, specials, statics):
            ## complete neighbor set
            neighbors = []
            for action in self.action_set:
                n_orig_state, n_action, n_reward, n_new_state, _ = \
                    self.simulator.sim(root.node.state, action,
                                       specials=specials, walls=statics)
                neighbors.append(n_new_state)
            return neighbors