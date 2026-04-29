from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Event:
    id: str
    type: str  # e.g., 'crime', 'fire'
    location_id: str
    start_time: float
    active: bool = True
    guards_needed: int = 2
    resolution_start_time: float | None = None
    details: dict[str, Any] = field(default_factory=dict)
