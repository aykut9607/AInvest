"""Local open-source models served by Ollama (/api/chat). No user data leaves the machine.

Three ways of talking to a model, each behind a small protocol so tests and the evaluation can pass fakes:
  chat          system + user -> text                       (coach explanations, router answers)
  chat_json     system + user + JSON schema -> dict          (router: pick intents from a closed list)
  chat_messages messages + tool definitions -> message       (tools mode: the model decides which tool to call)
"""

import json
from typing import Any, Protocol

import httpx


class LlmUnavailable(Exception):
    """The model could not be reached or answered with an error; the caller falls back to the template."""


class ChatModel(Protocol):
    model: str

    def chat(self, system: str, user: str) -> str: ...


class JsonChatModel(ChatModel, Protocol):
    def chat_json(self, system: str, user: str, schema: dict) -> dict: ...


class ToolChatModel(Protocol):
    model: str

    def chat_messages(self, messages: list[dict], tools: list[dict]) -> dict: ...


class OllamaChatModel:
    def __init__(self, base_url: str, model: str, timeout_seconds: float):
        self.model = model
        self._url = base_url.rstrip("/") + "/api/chat"
        self._timeout = timeout_seconds

    def _post(self, payload: dict) -> dict:
        try:
            response = httpx.post(self._url, json={"model": self.model, "stream": False, **payload},
                                  timeout=self._timeout)
            response.raise_for_status()
            return response.json().get("message", {})
        except (httpx.HTTPError, ValueError) as error:
            raise LlmUnavailable(f"{type(error).__name__}: {error}") from error

    def chat(self, system: str, user: str) -> str:
        message = self._post({
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            # low temperature: the same data should be explained the same way each time
            "options": {"temperature": 0.2, "num_predict": 400},
        })
        return message.get("content", "")

    def chat_json(self, system: str, user: str, schema: dict) -> dict:
        # Ollama constrains the output to the JSON schema (structured outputs); works without tool support
        message = self._post({
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": schema,
            "options": {"temperature": 0, "num_predict": 100},
        })
        try:
            value = json.loads(message.get("content", ""))
        except ValueError as error:
            raise LlmUnavailable(f"not JSON: {error}") from error
        if not isinstance(value, dict):
            raise LlmUnavailable("JSON is not an object")
        return value

    def chat_messages(self, messages: list[dict], tools: list[dict]) -> dict:
        return self._post({
            "messages": messages,
            "tools": tools,
            "options": {"temperature": 0.2, "num_predict": 500},
        })


def tool_calls(message: dict[str, Any]) -> list[tuple[str, dict, str | None]]:
    """(name, arguments, call id) of every tool call in a chat message (Ollama format); arguments may arrive as a
    JSON string. The id is passed back with the result so providers that pair calls and results by id can do so."""
    calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        arguments = function.get("arguments") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except ValueError:
                arguments = {}
        calls.append((str(function.get("name", "")), arguments if isinstance(arguments, dict) else {}, call.get("id")))
    return calls
