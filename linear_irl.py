import numpy as np
from cvxopt import matrix, solvers
from environments.gridworld import GridworldEnv
from environments.cliff_walking import CliffWalkingEnv
import matplotlib.pyplot as plt


def value_iteration(env, theta=0.001, discount_factor=0.9):
    """
    Value Iteration Algorithm.

    Args:
        env: OpenAI env. env.P represents the transition probabilities of the environment.
            env.P[s][a] is a list of transition tuples (prob, next_state, reward, done).
            env.nS is a number of states in the environment.
            env.nA is a number of actions in the environment.
        theta: We stop evaluation once our value function change is less than theta for all states.
        discount_factor: Gamma discount factor.

    Returns:
        A tuple (policy, V) of the optimal policy and the optimal value function.
    """

    def one_step_lookahead(state, V):
        """
        Helper function to calculate the value for all action in a given state.

        Args:
            state: The state to consider (int)
            V: The value to use as an estimator, Vector of length env.nS

        Returns:
            A vector of length env.nA containing the expected value of each action.
        """
        A = np.zeros(env.nA)
        for a in range(env.nA):
            for prob, next_state, reward, done in env.P[state][a]:
                A[a] += prob * (reward + discount_factor * V[next_state])
        return A

    V = np.zeros(env.nS)
    while True:
        # Stopping condition
        delta = 0
        # Update each state...
        for s in range(env.nS):
            # Do a one-step lookahead to find the best action
            A = one_step_lookahead(s, V)
            best_action_value = np.max(A)
            # Calculate delta across all states seen so far
            delta = max(delta, np.abs(best_action_value - V[s]))
            # Update the value function. Ref: Sutton book eq. 4.10.
            V[s] = best_action_value
            # Check if we can stop
        if delta < theta:
            break

    # Create a deterministic policy using the optimal value function
    policy = np.zeros([env.nS, env.nA])
    for s in range(env.nS):
        # One step lookahead to find the best action for this state
        A = one_step_lookahead(s, V)
        best_action = np.argmax(A)
        # Always take the best action
        policy[s, best_action] = 1.0

    return policy, V


def normalise(vals):
    min_val = np.min(vals)
    max_val = np.max(vals)
    return (vals - min_val) / (max_val - min_val)


def linear_irl(trans_probs, policy, gamma=0.9, l1=10, r_max=1):
    number_of_states = trans_probs.shape[0]
    number_of_actions = trans_probs.shape[2]

    # Formulate a linear IRL problem
    A = np.zeros([2 * number_of_states * (number_of_actions + 1), 3 * number_of_states])
    b = np.zeros([2 * number_of_states * (number_of_actions + 1)])
    c = np.zeros([3 * number_of_states])

    for i in range(number_of_states):
        a_opt = np.argmax(policy[i])
        tmp_inv = np.linalg.inv(np.identity(number_of_states) - gamma * trans_probs[:, :, a_opt])

        cnt = 0
        for a in range(number_of_actions):
            if a != a_opt:
                A[i * (number_of_actions - 1) + cnt, :number_of_states] = - \
                    np.dot(trans_probs[i, :, a_opt] - trans_probs[i, :, a], tmp_inv)
                A[number_of_states * (number_of_actions - 1) + i * (number_of_actions - 1) + cnt, :number_of_states] = - \
                    np.dot(trans_probs[i, :, a_opt] - trans_probs[i, :, a], tmp_inv)
                A[number_of_states * (number_of_actions - 1) + i * (
                        number_of_actions - 1) + cnt, number_of_states + i] = 1
                cnt += 1

    for i in range(number_of_states):
        A[2 * number_of_states * (number_of_actions - 1) + i, i] = 1
        b[2 * number_of_states * (number_of_actions - 1) + i] = r_max

    for i in range(number_of_states):
        A[2 * number_of_states * (number_of_actions - 1) + number_of_states + i, i] = -1
        b[2 * number_of_states * (number_of_actions - 1) + number_of_states + i] = 0

    for i in range(number_of_states):
        A[2 * number_of_states * (number_of_actions - 1) + 2 * number_of_states + i, i] = 1
        A[2 * number_of_states * (number_of_actions - 1) + 2 * number_of_states + i, 2 * number_of_states + i] = -1

    for i in range(number_of_states):
        A[2 * number_of_states * (number_of_actions - 1) + 3 * number_of_states + i, i] = 1
        A[2 * number_of_states * (number_of_actions - 1) + 3 * number_of_states + i, 2 * number_of_states + i] = -1

    for i in range(number_of_states):
        c[number_of_states:2 * number_of_states] = -1
        c[2 * number_of_states:] = l1

    sol = solvers.lp(matrix(c), matrix(A), matrix(b))
    rewards = sol['x'][:number_of_states]
    rewards = normalise(rewards) * r_max
    return rewards


def irl(env, env_name='Grid World', gamma=0.3, l1=10, r_max=5):
    trans_probs = np.zeros((env.observation_space.n, env.observation_space.n, env.action_space.n))
    rewards = np.zeros(env.observation_space.n)
    for state, value in env.P.items():
        for action, value_2 in value.items():
            prob, next_state, reward, done = value_2[0]
            trans_probs[state][next_state][action] = prob
            rewards[next_state] = reward

    policy, values = value_iteration(env, discount_factor=gamma)

    recovered_rewards = linear_irl(trans_probs, policy, gamma, l1, r_max)
    _, recovered_values = value_iteration(env)

    fig = plt.figure()
    # TODO: Add spacing between title and plots
    fig.suptitle('Linear IRL on ' + env_name, fontsize=16)

    axs1 = fig.add_subplot(2, 2, 1, aspect='equal')
    fig.gca().invert_yaxis()
    fig.gca().xaxis.tick_top()
    c1 = axs1.pcolor(rewards.reshape(env.shape))
    axs1.set_title("Reward")
    fig.colorbar(c1, ax=axs1)

    axs2 = fig.add_subplot(2, 2, 2, aspect='equal')
    fig.gca().invert_yaxis()
    fig.gca().xaxis.tick_top()
    c2 = axs2.pcolor(values.reshape(env.shape))
    axs2.set_title("Value")
    fig.colorbar(c2, ax=axs2)

    axs3 = fig.add_subplot(2, 2, 3, aspect='equal')
    fig.gca().invert_yaxis()
    fig.gca().xaxis.tick_top()
    c3 = axs3.pcolor(np.array(recovered_rewards).reshape(env.shape))
    axs3.set_title("Recovered Reward")
    fig.colorbar(c3, ax=axs3)

    axs4 = fig.add_subplot(2, 2, 4, aspect='equal')
    fig.gca().invert_yaxis()
    fig.gca().xaxis.tick_top()
    c4 = axs4.pcolor(recovered_values.reshape(env.shape))
    axs4.set_title("Recovered Value")
    fig.colorbar(c4, ax=axs4)

    fig.show()


if __name__ == '__main__':
    size = 10
    env = GridworldEnv(shape=[size, size], targets=[size * size - 1], reward_value=5.0, punishment_value=-1.0)
    irl(env, env_name='Grid World')
    env2 = CliffWalkingEnv()
    irl(env2, 'Cliff Walking')
