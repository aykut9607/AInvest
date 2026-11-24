"""Hosted reference model (Claude) for the comparisons only.

It is deliberately NOT part of the AI service: in production the text stays on the local model (report, privacy
decision; CLAUDE.md: everything local, no spending). Here it serves as an upper reference for the local models, and
what it receives is exactly what a local model receives: data blocks built from synthetic profiles, nothing else.

It follows the service's model protocols, so the production pipelines (number check, language check, template
fallback, router and tools assistant) run unchanged:
  chat           coach explanations and router answers
  chat_json      router: pick intents from a closed list (structured outputs, output_config.format)
  chat_messages  tools mode: the service keeps the conversation in Ollama's message format; it is translated here,
                 and Claude's own content blocks (with its thinking) are sent back unchanged on the next turn
Failures raise LlmUnavailable. Sampling is left at the vendor's defaults. The key comes from ANTHROPIC_API_KEY (.env).

Gemini was tried as a second reference (2026-11-21) and left out: on the free tier the 3.x Flash models timed
out or were overloaded (503/504), 2.5 was closed to new users (404) and Gemini 4 had a quota of 0 (429).
"""

import copy
import json

import anthropic

from adapters.llm import LlmUnavailable


def _strict(schema: dict) -> dict:
    """Structured outputs want every object closed (additionalProperties: false); array limits are checked in code."""
    schema = copy.deepcopy(schema)

    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                node.setdefault("additionalProperties", False)
            node.pop("maxItems", None)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    return schema


class AnthropicChatModel:
    def __init__(self, model: str = "claude-opus-5-5", effort: str = "medium"):
        self.model = model
        self.effort = effort  # thinking is always on for Opus 5.5; effort sets its depth (medium is the default)
        self.client = anthropic.Anthropic(max_retries=5, timeout=180)  # SDK retries 429/5xx with backoff
        self.input_tokens = self.output_tokens = 0
        # tool_use id -> the full assistant content (thinking + tool_use blocks) it came in, to send back unchanged
        self._turns: dict[str, list] = {}

    def _create(self, **kwargs):
        config = {"effort": self.effort, **kwargs.pop("output_config", {})}
        try:
            response = self.client.messages.create(model=self.model, max_tokens=8000, output_config=config, **kwargs)
        except anthropic.APIError as error:
            raise LlmUnavailable(f"{type(error).__name__}: {error}") from error
        self.input_tokens += response.usage.input_tokens
        self.output_tokens += response.usage.output_tokens
        if response.stop_reason == "refusal":
            raise LlmUnavailable("model refused")
        return response

    @staticmethod
    def _text(response) -> str:
        return "".join(block.text for block in response.content if block.type == "text")

    def chat(self, system: str, user: str) -> str:
        return self._text(self._create(system=system, messages=[{"role": "user", "content": user}]))

    def chat_json(self, system: str, user: str, schema: dict) -> dict:
        response = self._create(system=system, messages=[{"role": "user", "content": user}],
                                output_config={"format": {"type": "json_schema", "schema": _strict(schema)}})
        try:
            value = json.loads(self._text(response))
        except ValueError as error:
            raise LlmUnavailable(f"not JSON: {error}") from error
        if not isinstance(value, dict):
            raise LlmUnavailable("JSON is not an object")
        return value

    def chat_messages(self, messages: list[dict], tools: list[dict]) -> dict:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        converted: list[dict] = []
        for m in messages:
            if m["role"] == "user":
                converted.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant" and m.get("tool_calls"):
                first_id = m["tool_calls"][0].get("id")
                converted.append({"role": "assistant", "content": self._turns[first_id]})
            elif m["role"] == "assistant":
                converted.append({"role": "assistant", "content": m.get("content") or ""})
            elif m["role"] == "tool":
                result = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
                # consecutive tool results go back together in one user turn
                if converted and converted[-1]["role"] == "user" and isinstance(converted[-1]["content"], list):
                    converted[-1]["content"].append(result)
                else:
                    converted.append({"role": "user", "content": [result]})

        claude_tools = [{"name": t["function"]["name"], "description": t["function"]["description"],
                         "input_schema": t["function"]["parameters"]} for t in tools]
        response = self._create(system=system, tools=claude_tools, messages=converted)

        calls = [block for block in response.content if block.type == "tool_use"]
        for block in calls:
            self._turns[block.id] = response.content
        return {
            "content": self._text(response),
            "tool_calls": [{"id": b.id, "function": {"name": b.name, "arguments": b.input}} for b in calls],
        }

    def usage(self) -> dict:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens}
