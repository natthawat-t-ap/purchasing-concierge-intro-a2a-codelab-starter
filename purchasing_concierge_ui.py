"""
Purchasing Concierge UI - A2A Direct Client

This Gradio UI communicates directly with a remote A2A agent
(digital-dashboard-ai) via the A2A protocol instead of Vertex AI Agent Engine.
"""

import gradio as gr
import uuid
from typing import List, Dict, Any
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


def send_a2a_message(message_text: str, context_id: str) -> SendMessageResponse:
    """Send a message to the remote A2A agent using JSON-RPC."""
    message_id = str(uuid.uuid4())

    payload = {
        "message": {
            "role": "user",
            "parts": [{"type": "text", "text": message_text}],
            "messageId": message_id,
            "contextId": context_id,
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


def respond(message: str, history: List[Dict[str, Any]], context_id: str):
    """Send the message to the A2A agent and return updated history + context."""
    history = history or []
    history.append({"role": "user", "content": message})

    try:
        send_response = send_a2a_message(message, context_id)
        response_text = extract_response_text(send_response)
    except requests.exceptions.ConnectionError:
        response_text = f"❌ Cannot connect to agent at {AGENT_URL}. Make sure the A2A server is running."
    except Exception as e:
        response_text = f"❌ Error: {str(e)}"

    history.append({"role": "assistant", "content": response_text})
    return history, "", context_id


def new_session():
    """Clear chat and create a new session (new context_id)."""
    return [], str(uuid.uuid4())


if __name__ == "__main__":
    with gr.Blocks(title="Digital Dashboard AI - A2A Client") as demo:
        gr.Markdown("# Digital Dashboard AI - A2A Client")
        gr.Markdown(f"Connected to A2A agent at `{AGENT_URL}`")

        # Hidden state for context_id (session)
        context_id = gr.State(value=str(uuid.uuid4()))

        chatbot = gr.Chatbot(type="messages", height=500)

        with gr.Row():
            msg = gr.Textbox(
                placeholder="Type your message...",
                show_label=False,
                scale=9,
            )
            send_btn = gr.Button("Send", scale=1, variant="primary")

        delete_btn = gr.Button("🗑️ New Session", variant="stop")

        # Send on enter or button click
        msg.submit(respond, [msg, chatbot, context_id], [chatbot, msg, context_id])
        send_btn.click(respond, [msg, chatbot, context_id], [chatbot, msg, context_id])

        # Delete button = new session (clear chat + new context_id)
        delete_btn.click(new_session, outputs=[chatbot, context_id])

    demo.launch(server_name="0.0.0.0", server_port=8080)
