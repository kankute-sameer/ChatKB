from app.core.llm.types import StreamEvent
from app.features.conversations.service import PartsAccumulator


def test_accumulator_keeps_reasoning_and_text() -> None:
    acc = PartsAccumulator()
    for event in (
        StreamEvent(type="reasoning-start", id="rsn_1"),
        StreamEvent(type="reasoning-delta", id="rsn_1", delta="Think "),
        StreamEvent(type="reasoning-delta", id="rsn_1", delta="first."),
        StreamEvent(type="reasoning-end", id="rsn_1"),
        StreamEvent(type="text-start", id="text_1"),
        StreamEvent(type="text-delta", id="text_1", delta="Answer."),
        StreamEvent(type="text-end", id="text_1"),
    ):
        acc.apply(event)
    parts = acc.finalize()
    assert parts == [
        {"type": "reasoning", "text": "Think first.", "state": "done"},
        {"type": "text", "text": "Answer.", "state": "done"},
    ]
