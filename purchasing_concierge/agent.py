from .purchasing_agent import PurchasingAgent
from dotenv import load_dotenv
import os
import litellm

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# --- Langfuse Observability Setup ---
# 1. LiteLLM callbacks: traces all LLM calls (prompts, completions, tokens, latency)
litellm.success_callback = ["langfuse"]
litellm.failure_callback = ["langfuse"]

# 2. OpenTelemetry instrumentation: traces full ADK agent lifecycle
#    (agent steps, tool calls, callbacks, sub-agent delegation)
from openinference.instrumentation.google_adk import GoogleADKInstrumentor

GoogleADKInstrumentor().instrument()

root_agent = PurchasingAgent(
    remote_agent_addresses=[
        os.getenv("DIGITAL_DASHBOARD_AGENT_URL", "http://localhost:80"),
    ]
).create_agent()
