import base64
import json
import requests
from datetime import datetime, timezone
from decouple import config
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from utils.helper_functions import format_response_to_json

class GeminiModel:
    def __init__(self, model, temperature=0, json_output=False):
        """
        Initialize the GeminiModel with model name, temperature, and optional JSON output mode.
        """
        self.temperature = temperature
        self.project_id = config("GCP_PROJECT_ID")
        self.model = model
        self.location = config("GCP_PROJECT_LOCATION", default="us-central1")
        self.json_output = json_output

        # 🔹 Load & Authenticate Service Account
        self.credentials = self.authenticate_service_account(self.load_service_account_key())

        # 🔹 Store Token & Expiry
        self.access_token = None
        self.token_expiry = datetime.now(timezone.utc)  # Default expiry time
        self.refresh_token()  # Get an initial valid token

        # 🔹 API Endpoint
        self.endpoint = (
            f"https://{self.location}-aiplatform.googleapis.com/v1/projects/{self.project_id}/"
            f"locations/{self.location}/publishers/google/models/{model}:streamGenerateContent"
        )

    def refresh_token(self):
        """
        Refresh the access token only if it's expired.
        """
        try:
            if not self.credentials.valid or self.credentials.expired:
                request = Request()
                self.credentials.refresh(request)
                self.access_token = self.credentials.token
                self.token_expiry = self.credentials.expiry or datetime.now(timezone.utc)
                self.headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json; charset=utf-8",
                }
        except Exception as e:
            raise ValueError(f"Failed to refresh token: {e}")

    @staticmethod
    def authenticate_service_account(service_account_info):
        """
        Authenticate using the service account information.
        Returns the authenticated credentials with the required scopes.
        """
        try:
            required_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
            return service_account.Credentials.from_service_account_info(
                service_account_info, scopes=required_scopes
            ).with_quota_project(config("GCP_PROJECT_ID"))
        except Exception as e:
            raise ValueError(f"Failed to authenticate service account: {e}")

    @staticmethod
    def load_service_account_key():
        """
        Load and decode the base64-encoded service account key from environment variables.
        Returns the decoded key as a dictionary.
        """
        encoded_key = config("GCP_SC_KEY_BASE64_ENCODED_STRING", default="")
        if not encoded_key:
            raise ValueError("Service account key is missing in environment variables.")
        try:
            decoded_key = base64.b64decode(encoded_key).decode("utf-8")
            return json.loads(decoded_key)
        except Exception as e:
            raise ValueError(f"Failed to decode service account key: {e}")

    def invoke(self, messages, generation_config=None):
        """
        Invoke the model with a list of messages, optional safety settings, and generation configurations.
        Returns the response as a HumanMessage object.
        """

        # 🔹 Refresh Token if Expired
        self.refresh_token()

        # 🔹 Prepare Prompt for JSON Output
        user_prompt = (
            f"{messages}. Your output must be JSON formatted. "
            f"Just return the specified JSON format, do not prepend your response with anything."
            if self.json_output
            else f"{messages}"
        )

        payload = {
            "contents": [{
                "role": "user",
                "parts": {"text": user_prompt}
            }],
            "generation_config": generation_config or {
                "temperature": self.temperature
            },
        }

        # 🔹 Ensure JSON Output Mode is Set
        if self.json_output:
            payload["generation_config"]["response_mime_type"] = "application/json"

        try:
            response = requests.post(self.endpoint, headers=self.headers, data=json.dumps(payload))
            response.raise_for_status()
            response_data = response.json()
            # 🔹 Extracting & Formatting Response Text
            response_text = ""
            for item in response_data:
                if "candidates" in item and isinstance(item["candidates"], list):
                    for candidate in item["candidates"]:
                        if "content" in candidate and "parts" in candidate["content"]:
                            for part in candidate["content"]["parts"]:
                                response_text += part["text"]
            if not response_text:
                raise ValueError("Response text is empty after processing.")
            # 🔹 Handle JSON Output
            if self.json_output:
                try:
                    response_text = json.dumps(json.loads(response_text))  # Ensure valid JSON
                except json.JSONDecodeError:
                    try:
                        response_text = format_response_to_json(response_text)  # Attempt reformatting
                    except json.JSONDecodeError:
                        raise ValueError("Invalid JSON response received from the model.")

            return response_text

        except (requests.RequestException, ValueError, KeyError) as e:
            error_message = f"Error invoking the model: {e}"
            print("ERROR:", error_message)
            return json.dumps({"error": error_message})
