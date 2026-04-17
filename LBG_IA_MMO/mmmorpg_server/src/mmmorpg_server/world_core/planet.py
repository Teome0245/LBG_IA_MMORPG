"""Configuration d'une planète (Phase 1 : Terre1 sphérique simplifiée)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanetConfig:
    id: str
    label: str
    radius: float = 1000.0  # m (échelle jeu ; placeholder)
