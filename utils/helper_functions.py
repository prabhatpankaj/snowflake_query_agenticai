from datetime import datetime, timezone
import json
import re
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import StateSnapshot, PregelTask

# ✅ Get the current UTC date and time
def get_current_utc_datetime():
    now_utc = datetime.now(timezone.utc)
    return now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")

# ✅ Safely extract `content` if present, else return as-is
def check_for_content(var):
    return getattr(var, "content", var) if var else var

# ✅ Extract JSON from AI response, removing noise and fixing formatting
def format_response_to_json(response_text):
    try:
        cleaned = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if not json_match:
            raise ValueError("No valid JSON structure found in response")
        
        json_str = json_match.group(0).replace("'", '"')  # Fix single quotes
        parsed_json = json.loads(json_str)  # ✅ Validate JSON format
        return json.dumps(parsed_json, indent=2, ensure_ascii=False)
    
    except Exception as e:
        return json.dumps({
            "error": "JSON processing failed",
            "details": str(e),
            "original_response": response_text
        }, indent=2)

# ✅ Recursively serialize objects into structured JSON
def serialize_event(event):
    """
    Recursively serializes events into structured JSON format while ensuring:
    - `formatted_response` is parsed as a dictionary, not a string.
    - Numeric values (like SQL query results) remain as integers/floats.
    """
    if isinstance(event, StateSnapshot):
        return {
            "type": "StateSnapshot",
            "values": serialize_event(event.values),
            "next_tasks": serialize_event(event.next),
            "config": serialize_event(event.config),
            "metadata": serialize_event(event.metadata),
            "created_at": event.created_at.isoformat() if isinstance(event.created_at, datetime) else str(event.created_at),
            "parent_config": serialize_event(event.parent_config) if event.parent_config else None,
            "tasks": [serialize_event(task) for task in event.tasks] if event.tasks else [],
        }
    
    elif isinstance(event, PregelTask):
        return {
            "task_id": event.id,
            "task_name": event.name,
            "task_path": event.path,
            "error": event.error or "No error reported",
            "interrupts": serialize_event(event.interrupts),
            "state": serialize_event(event.state),
            "result": serialize_event(event.result)
        }

    elif isinstance(event, BaseMessage):
        parsed_content = safe_json_parse(event.content)
        return {
            "type": "human" if isinstance(event, HumanMessage) else "system",
            "content": parsed_content
        }

    elif isinstance(event, (list, tuple)):
        return [serialize_event(item) for item in event]

    elif isinstance(event, dict):
        # Ensure formatted_response is correctly parsed from string to dict
        if "formatted_response" in event and isinstance(event["formatted_response"], str):
            event["formatted_response"] = safe_json_parse(event["formatted_response"])
        return {key: serialize_event(value) for key, value in event.items()}

    elif isinstance(event, datetime):
        return event.isoformat()

    return event

def safe_json_parse(value):
    """
    Attempts to parse JSON strings into objects.
    Ensures that `formatted_response` is stored as a dictionary, not a string.
    """
    if isinstance(value, str):
        try:
            parsed_value = json.loads(value)
            return convert_numbers(parsed_value)  # Convert numbers inside JSON
        except json.JSONDecodeError:
            return value  # Return original if not valid JSON
    return value

def convert_numbers(obj):
    """
    Recursively converts numeric string values to actual integers or floats.
    Ensures JSON fields like `total_quantity_sold` are not mistakenly stored as strings.
    """
    if isinstance(obj, dict):
        return {k: convert_numbers(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numbers(v) for v in obj]
    elif isinstance(obj, str) and obj.isdigit():  # Convert numeric strings to int
        return int(obj)
    elif isinstance(obj, str):
        try:
            return float(obj) if "." in obj else int(obj)  # Convert decimals to float
        except ValueError:
            return obj  # Keep as string if conversion fails
    return obj

