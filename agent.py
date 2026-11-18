"""Bounded ReAct loop for damaged-order resolution."""

from .gemini_client import GeminiAPIError
from .tool_schemas import TOOL_SCHEMAS

MAX_ITERATIONS = 5

SYSTEM_INSTRUCTION = """
You are a customer order resolution specialist. Use the provided tools; never invent order, stock,
eligibility, payment, or notification details. For a damaged-item request:
1. Call lookup_order first. If it fails, do not attempt a resolution; politely ask the customer to
   verify the order identifier.
2. If the order is exchange-eligible, call check_inventory for its item. If the order is not
   eligible, do not check inventory.
3. Exchange an eligible order when stock is available. Otherwise refund the order (ineligible or
   no stock). The tools enforce these conditions.
4. After a successful exchange or refund, call send_notification with the customer's email and a
   concise confirmation including the actual transaction reference. Do not claim that a real email
   was delivered; this demo records a simulated notification.
5. Use tool error results to recover or explain the issue. Never claim success after a failed tool.
Finish with a clear, polite summary. Do not expose internal reasoning or customer data beyond what
is needed to explain the resolution.
""".strip()


class ResolutionAgent:
    def __init__(self, client, dispatcher, max_iterations=MAX_ITERATIONS):
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        self.client = client
        self.dispatcher = dispatcher
        self.max_iterations = max_iterations

    def run(self, user_message):
        contents = [{"role": "user", "parts": [{"text": user_message}]}]
        for iteration in range(1, self.max_iterations + 1):
            response = self.client.generate(
                contents=contents,
                function_declarations=TOOL_SCHEMAS,
                system_instruction=SYSTEM_INSTRUCTION,
            )
            candidate = first_candidate(response)
            if candidate is None:
                raise GeminiAPIError("Gemini returned no response candidate.")
            model_content = candidate.get("content")
            if not isinstance(model_content, dict):
                raise GeminiAPIError("Gemini returned a malformed response candidate.")
            parts = model_content.get("parts", [])
            if not isinstance(parts, list):
                raise GeminiAPIError("Gemini returned malformed response parts.")

            function_calls = []
            for part in parts:
                if isinstance(part, dict) and "functionCall" in part:
                    call = part["functionCall"]
                    if not isinstance(call, dict):
                        call = {}
                    function_calls.append(call)
            if not function_calls:
                text = "\n".join(
                    part["text"]
                    for part in parts
                    if isinstance(part, dict) and isinstance(part.get("text"), str)
                ).strip()
                return {
                    "response": text or "I could not produce a response. Please contact support.",
                    "escalated": False,
                    "iterations": iteration,
                }

            contents.append(model_content)
            function_responses = []
            for call in function_calls:
                name = call.get("name")
                if not isinstance(name, str):
                    name = ""
                result = self.dispatcher.dispatch(name, call.get("args"))
                function_responses.append(
                    {"functionResponse": {"name": name or "unknown", "response": result}}
                )
            contents.append({"role": "user", "parts": function_responses})

        return {
            "response": (
                "I could not safely complete this request within the allowed steps. "
                "Please contact customer support for a manual review."
            ),
            "escalated": True,
            "iterations": self.max_iterations,
        }


def first_candidate(response):
    if not isinstance(response, dict):
        return None
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    candidate = candidates[0]
    return candidate if isinstance(candidate, dict) else None
