"""
Purchasing Concierge UI - A2A Direct Client

This Gradio UI communicates directly with a remote A2A agent
(digital-dashboard-ai) via the A2A protocol.
"""

import gradio as gr
import uuid
import json
from typing import List, Dict, Any
from dotenv import load_dotenv
import os
import requests

load_dotenv()

AGENT_URL = os.getenv("DIGITAL_DASHBOARD_AGENT_URL", "http://localhost:80")


def send_a2a_message(message_text: str, context_id: str) -> dict:
    """Send a message to the remote A2A agent using JSON-RPC message/send."""
    message_id = str(uuid.uuid4())

    rpc_payload = {
        "jsonrpc": "2.0",
        "id": message_id,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": message_text}],
                "messageId": message_id,
                "contextId": context_id,
            }
        },
    }

    response = requests.post(AGENT_URL, json=rpc_payload, timeout=180)
    response.raise_for_status()
    return response.json()


def extract_text_from_response(resp_json: dict) -> str:
    """Extract text from raw JSON-RPC response dict."""
    # Check for JSON-RPC error
    if "error" in resp_json:
        err = resp_json["error"]
        return f"Agent error ({err.get('code', '?')}): {err.get('message', 'Unknown')}"

    result = resp_json.get("result", {})

    texts = []

    # Extract from artifacts
    for artifact in result.get("artifacts", []):
        for part in artifact.get("parts", []):
            t = _get_text(part)
            if t:
                texts.append(t)

    # Extract from status message
    status = result.get("status", {})
    status_msg = status.get("message")
    if status_msg:
        # status.message can have parts directly
        for part in status_msg.get("parts", []):
            t = _get_text(part)
            if t:
                texts.append(t)

    if texts:
        return "\n\n".join(texts)

    # Fallback: dump the result
    return f"```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```"


def _get_text(part: dict) -> str | None:
    """Extract text from a part dict, handling nested 'root' wrapper."""
    if "text" in part:
        return part["text"]
    root = part.get("root", {})
    if root and "text" in root:
        return root["text"]
    return None


def add_user_message(message: str, history: List[Dict[str, Any]]):
    """Append user message to history and clear input immediately."""
    history = history or []
    history.append({"role": "user", "content": message})
    return history, ""


def bot_respond(history: List[Dict[str, Any]], context_id: str):
    """Call the A2A agent and append the response."""
    if not history:
        return

    user_message = history[-1]["content"]

    try:
        resp_json = send_a2a_message(user_message, context_id)
        response_text = extract_text_from_response(resp_json)
    except requests.exceptions.ConnectionError:
        response_text = f"❌ Cannot connect to agent at {AGENT_URL}. Make sure the A2A server is running."
    except requests.exceptions.Timeout:
        response_text = "❌ Request timed out. The agent may be processing a complex query."
    except Exception as e:
        response_text = f"❌ Error: {str(e)}"

    history.append({"role": "assistant", "content": response_text})
    yield history


def new_session():
    """Clear chat and create a new session (new context_id)."""
    return [], str(uuid.uuid4())


if __name__ == "__main__":
    with gr.Blocks(title="Digital Dashboard AI - A2A Client") as demo:
        gr.Markdown("# Digital Dashboard AI - A2A Client")
        gr.Markdown(f"Connected to A2A agent at `{AGENT_URL}`")

        context_id = gr.State(value=str(uuid.uuid4()))
        chatbot = gr.Chatbot(type="messages", height=500)

        with gr.Row():
            msg = gr.Textbox(
                placeholder='Type message or JSON e.g. {"empcode":"AP005032","message":"ขอด lead"}',
                show_label=False,
                scale=9,
            )
            send_btn = gr.Button("Send", scale=1, variant="primary")

        delete_btn = gr.Button("🗑️ New Session", variant="stop")

        msg.submit(
            add_user_message, [msg, chatbot], [chatbot, msg]
        ).then(
            bot_respond, [chatbot, context_id], [chatbot]
        )
        send_btn.click(
            add_user_message, [msg, chatbot], [chatbot, msg]
        ).then(
            bot_respond, [chatbot, context_id], [chatbot]
        )

        delete_btn.click(new_session, outputs=[chatbot, context_id])

    demo.launch(server_name="0.0.0.0", server_port=8080)
