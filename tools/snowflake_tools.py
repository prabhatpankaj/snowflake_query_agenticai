import snowflake.connector
from states.agent_state import AgentGraphState
from decouple import config

def execute_snowflake_query(state: AgentGraphState, sql_query):
    """
    Executes a SQL query on Snowflake and updates the agent state with the results.
    """
    conn = snowflake.connector.connect(
        user=config("SNOWFLAKE_USER"),
        password=config("SNOWFLAKE_PASSWORD"),
        account=config("SNOWFLAKE_ACCOUNT"),
        database=config("SNOWFLAKE_DATABASE"),
        schema=config("SNOWFLAKE_SCHEMA"),
        warehouse=config("SNOWFLAKE_WAREHOUSE")
    )
    
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query)
        result = cursor.fetchall()
        state["sql_result"] = result
        return state
    except Exception as e:
        state["sql_result"] = f"Error executing SQL: {str(e)}"
        return state
    finally:
        cursor.close()
        conn.close()
