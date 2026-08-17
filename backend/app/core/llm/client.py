import base64
import json
from collections.abc import AsyncIterator, Sequence
from io import BytesIO
from typing import Any

import httpx
from PIL import Image

from app.core.config import Settings, get_settings
from app.core.llm.types import ChatMessage, StreamEvent
from app.core.log import AppLogger, get_logger
from app.core.retry import is_transient, retry_async

IMAGE_DESCRIPTION_PROMPT = (
    "Describe this image concisely for search and retrieval. If it contains text, "
    "tables, charts, or data, transcribe them accurately (exact values, labels, "
    "and table contents). If it is a photo or diagram, describe what it depicts. "
    "Output only the description."
)


class LLMClient:
    """RAW OPENAI CHUNK Responses API client that emits UI-message StreamEvents."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        title_model: str,
        vision_model: str = "gpt-5.6-luna",
        reasoning_effort: str = "medium",
        reasoning_summary: str = "auto",
        http: httpx.AsyncClient | None = None,
        log: AppLogger | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._title_model = title_model
        self._vision_model = vision_model
        self._reasoning_effort = reasoning_effort
        self._reasoning_summary = reasoning_summary
        self._http = http
        self._owns_http = http is None
        self.log = log.child("llm") if log is not None else get_logger("chatkb.llm")

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        log: AppLogger | None = None,
    ) -> "LLMClient":
        cfg = settings or get_settings()
        return cls(
            api_key=cfg.llm_api_key,
            base_url=cfg.llm_base_url,
            model=cfg.llm_model,
            title_model=cfg.llm_title_model,
            vision_model=cfg.llm_vision_model,
            reasoning_effort=cfg.llm_reasoning_effort,
            reasoning_summary=cfg.llm_reasoning_summary,
            log=log,
        )

    async def aclose(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(120.0),
            )
        return self._http

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _post_response(
        self,
        client: httpx.AsyncClient,
        body: dict[str, Any],
        headers: dict[str, str],
    ) -> httpx.Response:
        async def request() -> httpx.Response:
            response = await client.post(
                "/responses",
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            return response

        return await retry_async(request, retry_on=is_transient)

    @property
    def model_name(self) -> str:
        return self._model

    def _body(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str,
        stream: bool,
        with_reasoning: bool = False,
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "input": list(messages),
            "stream": stream,
            "store": False,
        }
        if tools:
            body["tools"] = list(tools)
        if with_reasoning and self._reasoning_effort not in ("", "off"):
            body["reasoning"] = {
                "effort": self._reasoning_effort,
                "summary": self._reasoning_summary,
            }
        return body

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
    ) -> str:
        client = await self._client()
        body = self._body(messages, model=model or self._title_model, stream=False)
        headers = self._headers()
        self.log.curl("POST", f"{self._base_url}/responses", headers, body)
        response = await self._post_response(client, body, headers)
        payload = response.json()
        self.log.debug("RAW OPENAI CHUNK << %s", payload)
        return _output_text(payload)

    async def describe_image(self, image: Image.Image) -> str:
        try:
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            body: dict[str, Any] = {
                "model": self._vision_model,
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": IMAGE_DESCRIPTION_PROMPT,
                            },
                            {
                                "type": "input_image",
                                "image_url": f"data:image/png;base64,{encoded}",
                            },
                        ],
                    }
                ],
                "stream": False,
                "store": False,
            }
            client = await self._client()
            headers = self._headers()
            self.log.debug(
                "OPENAI VISION REQUEST: model=%s image_bytes=%s",
                self._vision_model,
                len(buffer.getvalue()),
            )
            response = await self._post_response(client, body, headers)
            payload = response.json()
            return _output_text(payload)
        except Exception as exc:
            self.log.warning("image description skipped: %s", exc)
            return ""

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        client = await self._client()
        mapper = _ResponsesMapper()
        failed = False
        body = self._body(
            messages,
            model=model or self._model,
            stream=True,
            with_reasoning=True,
            tools=tools,
        )
        headers = self._headers()
        self.log.curl("POST", f"{self._base_url}/responses", headers, body)

        async def open_stream() -> tuple[
            httpx.Response,
            AsyncIterator[dict[str, Any]],
            dict[str, Any] | None,
        ]:
            request = client.build_request(
                "POST",
                "/responses",
                json=body,
                headers=headers,
            )
            response = await client.send(request, stream=True)
            try:
                response.raise_for_status()
                payloads = _iter_sse_payloads(response, log=self.log)
                first_payload = await anext(payloads, None)
                return response, payloads, first_payload
            except Exception:
                await response.aclose()
                raise

        try:
            response, payloads, first_payload = await retry_async(
                open_stream,
                retry_on=is_transient,
            )
        except Exception as exc:
            self.log.warning("LLM stream failed before output began: %s", exc)
            yield StreamEvent(
                type="error",
                errorText="The model failed to complete.",
            )
            return

        try:
            if first_payload is not None:
                for event in mapper.handle(first_payload):
                    if event.get("type") == "error":
                        failed = True
                    yield event
            async for payload in payloads:
                for event in mapper.handle(payload):
                    if event.get("type") == "error":
                        failed = True
                    yield event
        except Exception as exc:
            failed = True
            self.log.warning("LLM stream failed after output began: %s", exc)
            yield StreamEvent(
                type="error",
                errorText="The model failed to complete.",
            )
        finally:
            await response.aclose()
        if not failed:
            for event in mapper.close():
                yield event
            yield StreamEvent(type="finish-step")
            yield StreamEvent(type="finish")


async def _iter_sse_payloads(
    response: httpx.Response,
    log: AppLogger | None = None,
) -> AsyncIterator[dict[str, Any]]:
    data_lines: list[str] = []
    async for raw in response.aiter_lines():
        line = raw.rstrip("\r")
        if line == "":
            payload = _parse_sse_data(data_lines, log=log)
            data_lines = []
            if payload is not None:
                yield payload
            continue
        if line.startswith(":"):
            continue
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    payload = _parse_sse_data(data_lines, log=log)
    if payload is not None:
        yield payload


def _parse_sse_data(
    data_lines: list[str],
    log: AppLogger | None = None,
) -> dict[str, Any] | None:
    if not data_lines:
        return None
    data = "\n".join(data_lines).strip()
    if data == "":
        return None
    if log is not None:
        log.debug("RAW OPENAI CHUNK : %s", data)
    if data == "[DONE]":
        return None
    parsed: object = json.loads(data)
    if not isinstance(parsed, dict):
        return None
    return parsed


def _output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    chunks: list[str] = []
    output = payload.get("output") or []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content") or []
            if not isinstance(content, list):
                continue
            for part in content:
                if (
                    isinstance(part, dict)
                    and part.get("type") == "output_text"
                    and isinstance(part.get("text"), str)
                ):
                    chunks.append(part["text"])
    return "".join(chunks).strip()


class _ResponsesMapper:
    """Maps Responses API events onto the UI-message StreamEvent protocol."""

    def __init__(self) -> None:
        self._open_text: dict[str, str] = {}
        self._open_reasoning: dict[str, str] = {}
        self._tool_names: dict[str, str] = {}
        self._call_ids: dict[str, str] = {}

    def handle(self, payload: dict[str, Any]) -> list[StreamEvent]:
        event_type = payload.get("type")
        if event_type == "response.reasoning_summary_text.delta":
            return self._on_reasoning_delta(payload)
        if event_type == "response.reasoning_summary_text.done":
            return self._on_reasoning_done(payload)
        if event_type == "response.output_text.delta":
            return self._on_text_delta(payload)
        if event_type == "response.output_text.done":
            return self._on_text_done(payload)
        if event_type == "response.output_item.added":
            return self._on_output_item_added(payload)
        if event_type == "response.function_call_arguments.delta":
            return self._on_tool_delta(payload)
        if event_type == "response.function_call_arguments.done":
            return self._on_tool_done(payload)
        if event_type == "response.completed":
            return [self._response_metadata(payload)]
        if event_type in {"response.failed", "error"}:
            return [StreamEvent(type="error", errorText=_error_text(payload))]
        return []

    def _response_metadata(self, payload: dict[str, Any]) -> StreamEvent:
        response = payload.get("response")
        if not isinstance(response, dict):
            response = {}
        raw_usage = response.get("usage")
        usage: dict[str, int] = {}
        if isinstance(raw_usage, dict):
            for source, target in (
                ("input_tokens", "input_tokens"),
                ("output_tokens", "output_tokens"),
                ("total_tokens", "total_tokens"),
            ):
                value = raw_usage.get(source)
                if isinstance(value, int):
                    usage[target] = value
        status = str(response.get("status") or "completed")
        incomplete = response.get("incomplete_details")
        if isinstance(incomplete, dict) and incomplete.get("reason"):
            status = str(incomplete["reason"])
        return StreamEvent(
            type="response-metadata",
            usage=usage,
            finishReason=status,
            model=str(response.get("model") or ""),
        )

    def close(self) -> list[StreamEvent]:
        events: list[StreamEvent] = []
        for reasoning_id in list(self._open_reasoning):
            events.append(StreamEvent(type="reasoning-end", id=reasoning_id))
            del self._open_reasoning[reasoning_id]
        for text_id in list(self._open_text):
            events.append(StreamEvent(type="text-end", id=text_id))
            del self._open_text[text_id]
        return events

    def _on_reasoning_delta(self, payload: dict[str, Any]) -> list[StreamEvent]:
        reasoning_id = _reasoning_id(payload)
        delta = payload.get("delta")
        if not isinstance(delta, str) or delta == "":
            return []
        events: list[StreamEvent] = []
        if reasoning_id not in self._open_reasoning:
            self._open_reasoning[reasoning_id] = ""
            events.append(StreamEvent(type="reasoning-start", id=reasoning_id))
        self._open_reasoning[reasoning_id] += delta
        events.append(StreamEvent(type="reasoning-delta", id=reasoning_id, delta=delta))
        return events

    def _on_reasoning_done(self, payload: dict[str, Any]) -> list[StreamEvent]:
        reasoning_id = _reasoning_id(payload)
        events: list[StreamEvent] = []
        if reasoning_id not in self._open_reasoning:
            text = payload.get("text")
            if isinstance(text, str) and text:
                events.append(StreamEvent(type="reasoning-start", id=reasoning_id))
                events.append(
                    StreamEvent(type="reasoning-delta", id=reasoning_id, delta=text)
                )
                self._open_reasoning[reasoning_id] = text
        if reasoning_id in self._open_reasoning:
            events.append(StreamEvent(type="reasoning-end", id=reasoning_id))
            del self._open_reasoning[reasoning_id]
        return events

    def _on_text_delta(self, payload: dict[str, Any]) -> list[StreamEvent]:
        text_id = _item_id(payload)
        delta = payload.get("delta")
        if not isinstance(delta, str) or delta == "":
            return []
        events: list[StreamEvent] = []
        if text_id not in self._open_text:
            self._open_text[text_id] = ""
            events.append(StreamEvent(type="text-start", id=text_id))
        self._open_text[text_id] += delta
        events.append(StreamEvent(type="text-delta", id=text_id, delta=delta))
        return events

    def _on_text_done(self, payload: dict[str, Any]) -> list[StreamEvent]:
        text_id = _item_id(payload)
        events: list[StreamEvent] = []
        if text_id not in self._open_text:
            text = payload.get("text")
            if isinstance(text, str) and text:
                events.append(StreamEvent(type="text-start", id=text_id))
                events.append(StreamEvent(type="text-delta", id=text_id, delta=text))
                self._open_text[text_id] = text
        if text_id in self._open_text:
            events.append(StreamEvent(type="text-end", id=text_id))
            del self._open_text[text_id]
        return events

    def _on_output_item_added(self, payload: dict[str, Any]) -> list[StreamEvent]:
        item = payload.get("item")
        if not isinstance(item, dict) or item.get("type") != "function_call":
            return []
        tool_id = _tool_id(item)
        item_id = item.get("id")
        name = str(item.get("name") or "tool")
        self._remember_tool(tool_id, name)
        if isinstance(item_id, str) and item_id:
            self._call_ids[item_id] = tool_id
            self._remember_tool(item_id, name)
        return [
            StreamEvent(
                type="tool-input-start",
                toolCallId=tool_id,
                toolName=name,
                providerExecuted=True,
            )
        ]

    def _on_tool_delta(self, payload: dict[str, Any]) -> list[StreamEvent]:
        tool_id = self._tool_call_id(payload)
        delta = payload.get("delta")
        events: list[StreamEvent] = []
        if tool_id not in self._tool_names:
            self._remember_tool(tool_id, "tool")
            events.append(
                StreamEvent(
                    type="tool-input-start",
                    toolCallId=tool_id,
                    toolName="tool",
                    providerExecuted=True,
                )
            )
        if isinstance(delta, str) and delta:
            events.append(
                StreamEvent(
                    type="tool-input-delta",
                    toolCallId=tool_id,
                    inputTextDelta=delta,
                )
            )
        return events

    def _tool_call_id(self, payload: dict[str, Any]) -> str:
        call_id = payload.get("call_id")
        if isinstance(call_id, str) and call_id:
            return call_id
        item_id = _item_id(payload)
        return self._call_ids.get(item_id, item_id)

    def _remember_tool(self, tool_id: str, name: str) -> None:
        if name and name != "tool":
            self._tool_names[tool_id] = name
        elif tool_id not in self._tool_names:
            self._tool_names[tool_id] = name or "tool"

    def _tool_name(self, tool_id: str, payload: dict[str, Any]) -> str:
        name = payload.get("name")
        if isinstance(name, str) and name and name != "tool":
            self._remember_tool(tool_id, name)
            return name
        stored = self._tool_names.get(tool_id)
        if stored:
            return stored
        item_id = _item_id(payload)
        return self._tool_names.get(item_id, "tool")

    def _on_tool_done(self, payload: dict[str, Any]) -> list[StreamEvent]:
        tool_id = self._tool_call_id(payload)
        name = self._tool_name(tool_id, payload)
        arguments = payload.get("arguments")
        parsed: dict[str, Any] = {}
        if isinstance(arguments, str) and arguments:
            try:
                value = json.loads(arguments)
            except json.JSONDecodeError:
                value = {"raw": arguments}
            if isinstance(value, dict):
                parsed = value
        events: list[StreamEvent] = []
        if tool_id not in self._tool_names:
            self._remember_tool(tool_id, name)
            events.append(
                StreamEvent(
                    type="tool-input-start",
                    toolCallId=tool_id,
                    toolName=name,
                    providerExecuted=True,
                )
            )
        events.append(
            StreamEvent(
                type="tool-input-available",
                toolCallId=tool_id,
                toolName=name,
                input=parsed,
                providerExecuted=True,
            )
        )
        return events


def _reasoning_id(payload: dict[str, Any]) -> str:
    item_id = _item_id(payload)
    index = payload.get("summary_index")
    if isinstance(index, int):
        return f"{item_id}:{index}"
    return item_id


def _item_id(payload: dict[str, Any]) -> str:
    item_id = payload.get("item_id") or payload.get("id")
    if isinstance(item_id, str) and item_id:
        return item_id
    return "text"


def _tool_id(item: dict[str, Any]) -> str:
    for key in ("call_id", "id"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return "tool"


def _error_text(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message
    if isinstance(error, str) and error:
        return error
    message = payload.get("message")
    if isinstance(message, str) and message:
        return message
    return "The model failed to complete."
