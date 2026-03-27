"""
Purchasing Concierge UI - A2A Direct Client

This Gradio UI communicates directly with a remote A2A agent
(digital-dashboard-ai) via the A2A protocol instead of Vertex AI Agent Engine.
"""

import gradio as gr
import uuid
import json
from typing import List, Dict, Any
from pprint import pformat
from dotenv import load_dotenv
import os
import requests

from a2a.types import (
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    Task,
)

load_dotenv()

AGENT_URL = os.getenv("DIGITAL_DASHBOARD_AGENT_URL", "http://localhost:80")
CONTEXT_ID = str(uuid.uuid4())


def send_a2a_message(message_text: str) -> SendMessageResponse:
    """Send a message to the remote A2A agent using JSON-RPC."""
    message_id = str(uuid.uuid4())

    payload = {
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": message_text}],
            "messageId": message_id,
            "contextId": CONTEXT_ID,
        },
    }

    request = SendMessageRequest(
        id=message_id,
        params=MessageSendParams.model_validate(payload),
    )

    rpc_payload = request.model_dump(mode="json", exclude_none=True)
    response = requests.post(AGENT_URL, json=rpc_payload, timeout=120)
    response.raise_for_status()
    return SendMessageResponse.model_validate(response.json())


def extract_response_text(send_response: SendMessageResponse) -> str:
    """Extract text content from A2A SendMessageResponse."""
    if not isinstance(send_response.root, SendMessageSuccessResponse):
        return f"Error: received non-success response:\n```\n{send_response.model_dump_json(indent=2)}\n```"

    result = send_response.root.result

    # Handle Task response
    if isinstance(result, Task):
        parts = []
        if result.artifacts:
            for artifact in result.artifacts:
                for part in artifact.parts:
                    if hasattr(part, "root") and hasattr(part.root, "text"):
                        parts.append(part.root.text)
                    elif hasattr(part, "text"):
                        parts.append(part.text)
        if result.status and result.status.message:
            status_msg = result.status.message
            if hasattr(status_msg, "root") and hasattr(status_msg.root, "text"):
                parts.append(status_msg.root.text)
            elif hasattr(status_msg, "parts"):
                for p in status_msg.parts:
                    if hasattr(p, "root") and hasattr(p.root, "text"):
                        parts.append(p.root.text)
                    elif hasattr(p, "text"):
                        parts.append(p.text)
        if parts:
            return "\n\n".join(parts)
        return f"Task completed with status: {result.status.state if result.status else 'unknown'}"

    # Handle Message response
    if hasattr(result, "parts"):
        texts = []
        for part in result.parts:
            if hasattr(part, "root") and hasattr(part.root, "text"):
                texts.append(part.root.text)
            elif hasattr(part, "text"):
                texts.append(part.text)
        if texts:
            return "\n\n".join(texts)

    return f"Response:\n```json\n{send_response.model_dump_json(indent=2, exclude_none=True)}\n```"


async def get_response_from_agent(
    message: str,
    history: List[Dict[str, Any]],
) -> str:
    """Send the message to the A2A agent and get a response."""
    try:
        send_response = send_a2a_message(message)
        response_text = extract_response_text(send_response)

        yield [
            gr.ChatMessage(
                role="assistant",
                content=response_text,
            )
        ]
    except requests.exceptions.ConnectionError:
        yield [
            gr.ChatMessage(
                role="assistant",
                content=f"❌ Cannot connect to agent at {AGENT_URL}. Make sure the A2A server is running.",
            )
        ]
    except Exception as e:
        yield [
            gr.ChatMessage(
                role="assistant",
                content=f"❌ Error: {str(e)}",
            )
        ]


if __name__ == "__main__":
    demo = gr.ChatInterface(
        get_response_from_agent,
        title="Digital Dashboard AI - A2A Client",
        description=f"Connected to A2A agent at {AGENT_URL}",
        type="messages",
    )

    demo.launch(
        server_name="0.0.0.0",
        server_port=8080,
    )
