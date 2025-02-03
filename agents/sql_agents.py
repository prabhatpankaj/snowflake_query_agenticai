import json
from states.agent_state import AgentGraphState
from models.gemini_models import GeminiModel
from tools.snowflake_tools import execute_snowflake_query

class Agent:
    def __init__(self, state: AgentGraphState, model=None, server="gemini", temperature=0):
        self.state = state
        self.model = model
        self.server = server
        self.temperature = temperature

    def get_llm(self, json_output=True):
        if self.server == 'gemini':
            return GeminiModel(
                model=self.model,
                temperature=self.temperature,
                json_output=json_output
            )
        else:
            return {"error": "Missing or wrong 'server' in request body."}
    
    def update_state(self, key, value):
        self.state[key] = value
        self.state[f"{key}_logs"].append(value)

class InputValidationAgent(Agent):
    def invoke(self, user_query):
        validation_prompt = f"""
        Validate if the following query is appropriate for generating an SQL query:
        {user_query}
        Consider 'ga_schema.sales_data' as the table, which has columns:
        - product_name (STRING)
        - quantity_sold (INT)
        - sale_date (DATE)
        The dataset contains data such as:
        ('Car Model I', 19, '2024-11-21'),
        ('Car Model I', 1, '2024-11-28'),
        ('Car Model G', 21, '2025-02-12'),
        ('Car Model H', 35, '2024-12-06').
        Return 'valid' or 'invalid' as JSON.
        """
        llm = self.get_llm(json_output=True)
        validation_result = llm.invoke(validation_prompt)
        if "invalid" in validation_result.lower():
            self.update_state("validation_status", "invalid")
            self.update_state("error_message", "The provided query is not appropriate for processing.")
        else:
            self.update_state("validation_status", "valid")
        
        return self.state

class SQLQueryAgent(Agent):
    def invoke(self, user_query):
        if self.state.get("validation_status") == "invalid":
            return self.state
        
        prompt = f"""
        You are an expert in SQL generation. Given the user's question, generate a valid Snowflake SQL query.
        
        ### Rules:
        1. Use the table `ga_schema.sales_data` for all queries.
        2. The table contains the following columns:
           - product_name (STRING)
           - quantity_sold (INT)
           - sale_date (DATE)
        3. The dataset includes entries such as:
           ('Car Model I', 19, '2024-11-21'),
           ('Car Model I', 1, '2024-11-28'),
           ('Car Model G', 21, '2025-02-12').
        4. Always return a valid JSON object in the format: 
           {{"query": "SQL_QUERY_HERE"}}
        5. Do not add explanations, extra text, or comments.
        6. If the query cannot be generated, return: {{"error": "Could not generate SQL"}}.
        
        ### User Input:
        {user_query}
        """
        llm = self.get_llm(json_output=True)
        sql_response = llm.invoke(prompt)
        try:
            sql_query = json.loads(sql_response)
            if "query" in sql_query:
                self.update_state("sql_query", sql_query["query"])
            else:
                self.update_state("sql_query", "ERROR: Could not generate SQL")
        except json.JSONDecodeError:
            self.update_state("sql_query", "ERROR: Invalid JSON response from Gemini")

        return self.state

class SQLExecutorAgent(Agent):
    def invoke(self, sql_query):
        """
        Invokes the SQL executor agent by extracting and executing a SQL query.
        Handles input formats flexibly and updates the agent state accordingly.
        """
        # If sql_query is a string, attempt to parse JSON
        if isinstance(sql_query, str):
            try:
                parsed_query = json.loads(sql_query)
            except json.JSONDecodeError:
                parsed_query = sql_query  # Keep it as a string if parsing fails
        else:
            parsed_query = sql_query

        # Extract actual query if given as a dictionary
        if isinstance(parsed_query, dict) and "query" in parsed_query:
            sql_query = parsed_query["query"]
        else:
            sql_query = parsed_query  # Use it directly if already a string

        # Validate that we have a proper SQL string
        if not isinstance(sql_query, str) or not sql_query.strip():
            self.update_state("sql_result", "ERROR: Invalid SQL format received")
            return self.state

        # Execute the SQL query
        self.state = execute_snowflake_query(self.state, sql_query)
        return self.state


class ResponseFormatterAgent(Agent):
    def invoke(self, sql_result):
        if callable(sql_result):
            sql_result = sql_result()
        
        prompt = f"""
        Consider 'ga_schema.sales_data' table with the following columns:
        - product_name (STRING)
        - quantity_sold (INT)
        - sale_date (DATE)
        The dataset contains data such as:
        ('Car Model I', 19, '2024-11-21'),
        ('Car Model I', 1, '2024-11-28'),
        ('Car Model G', 21, '2025-02-12').
        Convert the following SQL result into a human-readable response:
        {sql_result}
        """
        llm = self.get_llm()
        formatted_response = llm.invoke(prompt)
        self.update_state("formatted_response", formatted_response)
        return self.state