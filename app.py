from flask import Flask, request, jsonify
import logging
import base64
import uuid
from waitress import serve
from decouple import config
from agent_graph.graph import create_graph, compile_workflow
from utils.helper_functions import serialize_event

app = Flask(__name__)

DEBUG_MODE = config("DEBUG", "False").lower() in ["true", "1", "yes"]
temperature = int(config("LLM_TEMPERATURE", 0))
iterations = int(config("ITERATIONS", 40))
app.debug = DEBUG_MODE

logging_level = logging.DEBUG if DEBUG_MODE else logging.INFO
logging.basicConfig(
    level=logging_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
app.logger.info(f"🔍 Debug mode is {'ON' if DEBUG_MODE else 'OFF'}")

graph = create_graph(temperature=temperature)
workflow = compile_workflow(graph)

@app.route("/query", methods=["POST"])
def handle_query():
    try:
        data = request.get_json()
        query = data.get("query")
        thread_id = str(uuid.uuid4())

        limit = {
            "recursion_limit": iterations,
            "configurable": {
                "thread_id": str(thread_id),
                "checkpoint_ns": "youtube-summary"
            }
        }

        if not query:
            return jsonify({"error": "Missing 'query' in request body."}), 400
        
        dict_inputs = {"user_query": query}

        # ✅ Fetch and process events
        latest_event = None
        for event in workflow.stream(dict_inputs, limit):
            if "end_node" in event:
                latest_event = serialize_event(event)  # ✅ Serialize event
                break  # ✅ Stop after processing the first valid event
        
        if latest_event is None:
            return jsonify({"message": "Query processed, but no relevant data found."}), 200
        
        response_data = {
            "thread_id": thread_id,
            "values": latest_event
        }
        
        return jsonify(response_data)

    except Exception as e:
        app.logger.error(f"Error in handle_query: {e}")
        return jsonify({"error": str(e)}), 500

# Route to visualize the graph
@app.route("/visualize", methods=["GET"])
def visualize_graph():
    try:
        mermaid_syntax = workflow.get_graph().draw_mermaid()
        with open("workflow_graph.mmd", "w") as f:
            f.write(mermaid_syntax)

        output_file = "workflow_graph.png"
        workflow.get_graph().draw_mermaid_png(output_file_path=output_file)
        
        # Convert PNG to base64
        with open(output_file, "rb") as img_file:
            base64_image = base64.b64encode(img_file.read()).decode('utf-8')
        
        return jsonify({"message": "Graph visualization saved as base64 PNG.", "file": base64_image})
    except Exception as e:
        app.logger.error(f"Error in visualize_graph: {e}")
        return jsonify({"error": str(e), "message": "Failed to render graph as PNG. Try rendering manually."}), 500


@app.route("/history", methods=["GET"])
def get_conversation_history():
    """
    Retrieve the most recent conversation history for a user & thread from LangGraph checkpoints.
    Adjusts filtering logic to find the latest event without requiring `end_chain`.
    """
    try:
        # ✅ Get thread_id from request params
        thread_id = request.args.get("thread_id")

        config = {
            "configurable": {"thread_id": str(thread_id)},
            "recursion_limit": 100
        }

        print(f"Fetching history with config: {config}")

        # ✅ Fetch the last 5 history entries
        history = list(workflow.get_state_history(config))

        if not history:
            return jsonify({"message": "No conversation history found."}), 200


        # ✅ Extract the latest event containing `sql_result`
        latest_event = next(
            (event for event in history if hasattr(event, "values") and event.values.get("sql_result")),
            None
        )

        if latest_event is None:
            app.logger.warning(f"No valid `sql_result` found in history for thread_id={thread_id}.")
            return jsonify({"message": "No valid history found for the given thread."}), 200

        # ✅ Serialize event using the provided serialize_event function
        serialized_event = serialize_event(latest_event)

        # ✅ Extract key values to match required JSON format
        event_values = serialized_event.get("values", {})
        response_data = {
            "thread_id": thread_id,
            "values": {
                "end_node": {
                    "user_query": event_values.get("user_query", ""),
                    "sql_query": event_values.get("sql_query", ""),
                    "sql_result": event_values.get("sql_result", []),
                    "formatted_response": event_values.get("formatted_response", ""),
                    "formatted_response_logs": [
                        {
                            "content": event_values.get("formatted_response", ""),
                            "type": "human"
                        }
                    ],
                    "sql_query_logs": [
                        {
                            "content": event_values.get("sql_query", ""),
                            "type": "human"
                        }
                    ],
                    "sql_result_logs": event_values.get("sql_result_logs", []),
                    "query_logs": event_values.get("query_logs", []),
                    "response_logs": event_values.get("response_logs", []),
                    "execution_logs": event_values.get("execution_logs", []),
                    "validation_logs": event_values.get("validation_logs", []),
                    "end_chain": event_values.get("end_chain", [])
                }
            }
        }

        return jsonify(response_data), 200

    except Exception as e:
        app.logger.error(f"Error fetching history: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    if DEBUG_MODE:
        app.run(debug=True, host="0.0.0.0", port=8000)
    else:
        serve(app, host="0.0.0.0", port=8000)
