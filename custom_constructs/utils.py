import os, json
from aws_cdk import (aws_stepfunctions as stepfunctions)
def get_local_project_root():
    current = os.path.abspath(os.getcwd())
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "cdk.json")):
            return current
        current = os.path.dirname(current)
    else:
        raise RuntimeError("Could not find project root containing cdk.json")

def get_state_definition_json(chain:stepfunctions.IChainable):

    # print state and children
    def full_chain_json(state):
        # convert the current state
        state_json = state.to_state_json()

        # Recursive expand Map or Parallel branches
        if hasattr(state, "branches"):
            state_json["Branches"] = [full_chain_json(branch.start_state) for branch in state.branches]
        
        # Expand linear 'Next' states
        if hasattr(state, "next_state") and state.next_state:
            state_json["Next"]=state.next_state.id
        
        return state_json
    
    # All series states in chain
    states = chain.start_state.find_reachable_states(chain.start_state)

    # Make json-like definition and print
    definition={"StartAt":chain.start_state.id, "States":{}}
    for state in states:
        definition["States"][state.node.id]=full_chain_json(state)
    return json.dumps(definition, indent=2)