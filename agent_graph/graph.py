from langgraph.graph import StateGraph
from agents.sql_agents import (
    SQLQueryAgent,
    SQLExecutorAgent,
    ResponseFormatterAgent
)
from decouple import config
from states.agent_state import AgentGraphState, get_agent_graph_state
from db.mongo_connection import get_checkpointer

checkpointer = get_checkpointer()

def create_graph(temperature=0):
    graph = StateGraph(AgentGraphState)

    graph.add_node(
        "query_converter", 
        lambda state: SQLQueryAgent(
            state=state,
            model=config("QUERY_MODEL", "gemini-1.5-pro-002"),
        ).invoke(
            user_query=state["user_query"]
        )
    )

    graph.add_node(
        "sql_executor", 
        lambda state: SQLExecutorAgent(
            state=state,
            model=config("QUERY_MODEL", "gemini-1.5-pro-002"),
        ).invoke(
            sql_query=get_agent_graph_state(state=state, state_key="sql_query")
        )
    )

    graph.add_node(
        "response_formatter", 
        lambda state: ResponseFormatterAgent(
            state=state,
            model=config("QUERY_MODEL", "gemini-1.5-pro-002"),
        ).invoke(
            sql_result=get_agent_graph_state(state=state, state_key="sql_result")
        )
    )

    graph.add_node("end_node", lambda state: state)

    # Define the workflow sequence
    graph.set_entry_point("query_converter")
    graph.set_finish_point("end_node")
    graph.add_edge("query_converter", "sql_executor")
    graph.add_edge("sql_executor", "response_formatter")
    graph.add_edge("response_formatter", "end_node")

    return graph

def compile_workflow(graph):
    workflow = graph.compile(checkpointer=checkpointer)
    return workflow
