"""Field-name remapping so each bank can override canonical SYNC field names
to whatever they actually call them in their CRM instance.

Loads `FieldMapping` rows at adapter init; defaults to the canonical name
if no override exists. Adapters call `mapping.field("contact", "risk_score")`
instead of hard-coding the property name.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlmodel import select

from db import get_session
from db.models import FieldMapping


@dataclass
class FieldMapper:
    overrides: dict[tuple[str, str], str] = field(default_factory=dict)

    def field(self, object_type: str, canonical: str) -> str:
        return self.overrides.get((object_type, canonical), canonical)

    def contact(self, canonical: str) -> str:
        return self.field("contact", canonical)

    def deal(self, canonical: str) -> str:
        return self.field("deal", canonical)

    def task(self, canonical: str) -> str:
        return self.field("task", canonical)


_cache: dict[str, FieldMapper] = {}


async def load_mapper(connection_id: str) -> FieldMapper:
    """Build (and cache) a FieldMapper for the given connection."""
    if connection_id in _cache:
        return _cache[connection_id]
    overrides: dict[tuple[str, str], str] = {}
    async with get_session() as session:
        rows = (
            await session.exec(
                select(FieldMapping).where(FieldMapping.connection_id == connection_id)
            )
        ).all()
        for row in rows:
            overrides[(row.object_type, row.canonical_name)] = row.bank_field_name
    mapper = FieldMapper(overrides=overrides)
    _cache[connection_id] = mapper
    return mapper


def invalidate(connection_id: Optional[str] = None) -> None:
    """Drop cached mappers — call after PUT /field-mappings."""
    if connection_id is None:
        _cache.clear()
    else:
        _cache.pop(connection_id, None)
