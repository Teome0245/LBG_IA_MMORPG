from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Location:
    id: str
    name: str
    type: str  # e.g., 'planet', 'city', 'building', 'room'
    parent_id: str | None = None
    tags: list[str] = field(default_factory=list)
    geometry: dict[str, Any] = field(default_factory=dict)
