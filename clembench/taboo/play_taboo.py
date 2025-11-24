from clembench import taboo

mode = "mock"

idx_to_models = {
    0: "gpt3",
    1: "llama3-7b"
}

env = taboo.env()
env.reset()  # use default instance
for agent_id in env.agent_iter(max_iter=10):
    observation, reward, termination, truncation, info = env.last()
    if termination or truncation:
        action = None
    elif mode == "mock":
        action = env.action_space(agent_id).sample()
    else:
        action = idx_to_models[agent_id].generate_response(observation)
    print(agent_id.name, action)
    env.step(action)
env.close()
