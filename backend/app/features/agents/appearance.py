from __future__ import annotations

import secrets
from typing import Any

APPEARANCE_PRESETS = (
    "pink-blur",
    "blue-blur",
    "red-blur",
    "green-blur",
    "amber-blur",
    "violet-blur",
)


def random_appearance() -> dict[str, Any]:
    return {"type": "preset", "key": secrets.choice(APPEARANCE_PRESETS)}
