from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

# Define the state object for the SQL agent graph
class AgentGraphState(TypedDict):
    user_query: str
    validation_status: str
    error_message: str
    sql_query: str
    sql_result: list
    formatted_response: str
    validation_logs: Annotated[list, add_messages]
    query_logs: Annotated[list, add_messages]
    execution_logs: Annotated[list, add_messages]
    response_logs: Annotated[list, add_messages]
    sql_query_logs: Annotated[list, add_messages]  # ✅ Added missing logs
    sql_result_logs: Annotated[list, add_messages]  # ✅ Added missing logs
    formatted_response_logs: Annotated[list, add_messages]  # ✅ Added missing logs
    end_chain: Annotated[list, add_messages]

# Define the nodes in the agent graph
def get_agent_graph_state(state: AgentGraphState, state_key: str):
    if state_key in state:
        return state[state_key]  # ✅ Now dynamically returns any state key if present
    else:
        return None  # ✅ Returns None if the key doesn't exist

# Initialize state
state = {
    "user_query": "",
    "validation_status": "",
    "error_message": "",
    "sql_query": "",
    "sql_result": [],
    "formatted_response": "",
    "validation_logs": [],
    "query_logs": [],
    "execution_logs": [],
    "response_logs": [],
    "sql_query_logs": [],  # ✅ Now matches the TypedDict
    "sql_result_logs": [],  # ✅ Now matches the TypedDict
    "formatted_response_logs": [],  # ✅ Now matches the TypedDict
    "end_chain": []
}
