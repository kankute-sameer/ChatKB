from app.core.llm.client import LLMClient, _ResponsesMapper


def test_stream_body_includes_reasoning() -> None:
    client = LLMClient(
        api_key="k",
        base_url="https://example.test/v1",
        model="gpt-5-mini",
        title_model="gpt-4.1-mini",
        reasoning_effort="medium",
        reasoning_summary="auto",
    )
    body = client._body([], model="gpt-5-mini", stream=True, with_reasoning=True)
    assert body["reasoning"] == {"effort": "medium", "summary": "auto"}


def test_complete_body_omits_reasoning() -> None:
    client = LLMClient(
        api_key="k",
        base_url="https://example.test/v1",
        model="gpt-5-mini",
        title_model="gpt-4.1-mini",
    )
    body = client._body([], model="gpt-4.1-mini", stream=False)
    assert "reasoning" not in body


def test_reasoning_off_omits_field() -> None:
    client = LLMClient(
        api_key="k",
        base_url="https://example.test/v1",
        model="gpt-5-mini",
        title_model="gpt-4.1-mini",
        reasoning_effort="off",
    )
    body = client._body([], model="gpt-5-mini", stream=True, with_reasoning=True)
    assert "reasoning" not in body


def test_mapper_streams_reasoning_then_text() -> None:
    mapper = _ResponsesMapper()
    events = [
        *mapper.handle(
            {
                "type": "response.reasoning_summary_text.delta",
                "item_id": "rs_1",
                "summary_index": 0,
                "delta": "Consider ",
            }
        ),
        *mapper.handle(
            {
                "type": "response.reasoning_summary_text.delta",
                "item_id": "rs_1",
                "summary_index": 0,
                "delta": "the question.",
            }
        ),
        *mapper.handle(
            {
                "type": "response.reasoning_summary_text.done",
                "item_id": "rs_1",
                "summary_index": 0,
                "text": "Consider the question.",
            }
        ),
        *mapper.handle(
            {
                "type": "response.output_text.delta",
                "item_id": "msg_1",
                "delta": "Hello",
            }
        ),
        *mapper.handle({"type": "response.output_text.done", "item_id": "msg_1"}),
    ]
    types = [event["type"] for event in events]
    assert types == [
        "reasoning-start",
        "reasoning-delta",
        "reasoning-delta",
        "reasoning-end",
        "text-start",
        "text-delta",
        "text-end",
    ]
    reasoning = "".join(
        str(event.get("delta") or "")
        for event in events
        if event["type"] == "reasoning-delta"
    )
    assert reasoning == "Consider the question."
