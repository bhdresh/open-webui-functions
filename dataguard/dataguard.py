"""
title: DataGuard
author: Bhadresh Patel
version: 1.0
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
import requests
import json


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )
        OLLAMA_BASE_URL: str = Field(
            default="http://172.17.0.1:11434", description="Ollama URL."
        )
        OLLAMA_MODEL: str = Field(default="qwen2.5:32b", description="Ollama Model.")
        OLLAMA_CONTEXT: int = Field(default=30000, description="Ollama Context.")
        RESTRICTED_CATEGORIES: str = Field(
            default="1) Share highly confidential information with unauthorized individuals or external parties without proper approval. Examples of Highly Confidential Information: Financial Status/Records, financial transactions, IT infrastructure details.",
            description="Restricted categories.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(
        self,
        body: dict,
        __event_emitter__: None,
        __model__: Optional[dict] = None,
        __user__: Optional[dict] = None,
    ) -> dict:
        print(f"inlet:{__name__}")
        print(f"inlet:body:{body}")
        print(f"inlet:user:{__user__}")

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Checking your message and file content for safety...",
                        "done": False,
                    },
                }
            )

        messages = body.get("messages", [])
        files = body.get("files", [])

        user_last_message = messages[-1]["content"] if messages else ""

        # Extract content from files
        file_contents = []
        for file_entry in files:
            file_data = file_entry.get("file", {}).get("data", {})
            content = file_data.get("content", "")
            if content:
                file_contents.append(content)

        # Combine user message and file contents
        check_contents = user_last_message + " " + " ".join(file_contents)

        # Self valve parameters
        OLLAMA_BASE_URL = self.valves.OLLAMA_BASE_URL
        OLLAMA_MODEL = self.valves.OLLAMA_MODEL
        OLLAMA_CONTEXT = self.valves.OLLAMA_CONTEXT
        RESTRICTED_CATEGORIES = self.valves.RESTRICTED_CATEGORIES
        OPTIONS = {"num_ctx": self.valves.OLLAMA_CONTEXT}
        STREAM = False

        # Create a system message
        system_message = {
            "role": "system",
            "content": (
                f"You are DataGuard LLM. Analyze the provided input and check if it matches any of "
                f"the provided restrictions. RESTRICTIONS LIST: {RESTRICTED_CATEGORIES}. "
                f"If a match is found, reply by stating the matched restriction with a brief description. "
                'Format the output as JSON: { "RESTRICTION_MATCH": "Yes", "REASON": "JUSTIFICATION TEXT" }'
            ),
        }

        # Prepare the prompt and updated user message
        updated_user_message = {"role": "user", "content": check_contents}

        # Create the new messages list with system and user messages
        new_messages = [system_message, updated_user_message]

        try:
            response = requests.post(
                url=f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": new_messages,
                    "options": OPTIONS,
                    "stream": STREAM,
                },
            )
            response.raise_for_status()
            api_response = response.json()
            assistant_message = (
                api_response.get("message", {}).get("content", "").strip().lower()
            )
            print("####################################")
            print(assistant_message)
            print("####################################")
            data = json.loads(assistant_message)
            if data.get("restriction_match", "").lower() == "yes":
                reason = data.get("reason")
                new_user_message_content = (
                    f"Inform user that user supplied restricted data hence "
                    f"his query is dropped. Reason: {reason}"
                )
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Your message security check failed",
                            "done": True,
                        },
                    }
                )
            else:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Your message security check Passed",
                            "done": True,
                        },
                    }
                )
                new_user_message_content = user_last_message

        except requests.RequestException as e:
            print(f"Request error from Ollama API: {e}")
            return {"error": str(e)}

        if new_user_message_content is not None:
            new_user_message = {"role": "user", "content": new_user_message_content}
            print("###################################")
            print(new_user_message)
            print("###################################")
            body["messages"][-1] = new_user_message

        return body
