from __future__ import annotations

import re
import secrets

from app.core.citations.sources import Source

CITE_RE = re.compile(r"\[cite:([^\]]+)\]")


class Citations:
    """Per-generation, in-memory. Holds cite_id -> Source, then discarded."""

    def __init__(self) -> None:
        self._by_id: dict[str, Source] = {}
        self._id_by_key: dict[str, str] = {}
        self._order: list[str] = []

    def add(self, source: Source) -> str:
        key = source.dedup_key()
        existing = self._id_by_key.get(key)
        if existing is not None:
            return existing
        cite_id = secrets.token_hex(4)
        while cite_id in self._by_id:
            cite_id = secrets.token_hex(4)
        self._by_id[cite_id] = source
        self._id_by_key[key] = cite_id
        self._order.append(cite_id)
        return cite_id

    def known_ids(self) -> set[str]:
        return set(self._by_id)

    def get(self, cite_id: str) -> Source | None:
        return self._by_id.get(cite_id)

    def validate(self, text: str) -> str:
        known = self._by_id

        def _keep(match: re.Match[str]) -> str:
            cite_id = match.group(1)
            return match.group(0) if cite_id in known else ""

        return CITE_RE.sub(_keep, text)

    def source_parts(self) -> list[dict[str, object]]:
        return [
            self._by_id[cite_id].to_source_part(cite_id) for cite_id in self._order
        ]
