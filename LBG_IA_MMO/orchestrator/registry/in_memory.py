from __future__ import annotations

from collections.abc import Iterable

from capabilities.spec import CapabilitySpec


class InMemoryCapabilityRegistry:
    def __init__(self, specs: Iterable[CapabilitySpec] | None = None) -> None:
        self._by_name: dict[str, CapabilitySpec] = {}
        if specs:
            for s in specs:
                self.register(s)

    def register(self, spec: CapabilitySpec) -> None:
        self._by_name[spec.name] = spec

    def list(self) -> list[CapabilitySpec]:
        return sorted(self._by_name.values(), key=lambda s: s.name)

    def get(self, name: str) -> CapabilitySpec | None:
        return self._by_name.get(name)

