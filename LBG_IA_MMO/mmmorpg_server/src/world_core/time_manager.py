"""Temps monde : cycle jour/nuit sur DAY_CYCLE_SECONDS (plan : 6 h)."""

from __future__ import annotations

# Plan design : un cycle jour/nuit complet = 6 heures (21600 s).
DAY_CYCLE_SECONDS: float = 6 * 3600


class TimeManager:
    """Horloge serveur monotone ; `advance` appelée à chaque tick."""

    def __init__(self, *, day_cycle_seconds: float = DAY_CYCLE_SECONDS) -> None:
        self._cycle = day_cycle_seconds
        self.world_time_s: float = 0.0

    @property
    def day_fraction(self) -> float:
        """0 = minuit, 0.5 = midi, 1.0 → retour minuit."""
        return (self.world_time_s % self._cycle) / self._cycle

    def advance(self, dt: float) -> None:
        self.world_time_s += max(0.0, dt)
