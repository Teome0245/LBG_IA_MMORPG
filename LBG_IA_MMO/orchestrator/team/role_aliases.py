"""Alias affichables des rôles équipe (personas studio)."""

from __future__ import annotations

import json
import os

DEFAULT_ROLE_ALIASES: dict[str, dict[str, str]] = {
    "ops": {
        "alias": "Héphaïstos",
        "title": "Forgeron infra",
        "tagline": "Sondes Proxmox, stockage, Ollama",
    },
    "qa": {
        "alias": "Argus",
        "title": "Veille qualité",
        "tagline": "Smokes LAN et healthz",
    },
    "pm": {
        "alias": "Thémis",
        "title": "Pilotage projet",
        "tagline": "Jalons, roadmap, réunification",
    },
    "dev_game": {
        "alias": "Dédale",
        "title": "Forge gameplay",
        "tagline": "Core3, Godot, prototypes OpenGame",
    },
    "player_ia": {
        "alias": "Chœur du monde",
        "title": "Joueurs IA Prime",
        "tagline": "Lia, Nix… sur Core3 246",
    },
}

# Personas sous-projets (affichage tâches — rôle technique inchangé)
SUBPROJECT_PERSONAS: dict[str, dict[str, str]] = {
    "infographiste_ia": {
        "alias": "Pygmalion",
        "title": "Infographiste IA",
        "tagline": "Pipeline GLB, Blender, assets Godot",
        "owner_role": "dev_game",
    },
    "client_godot": {
        "alias": "Dédale",
        "title": "Client Godot",
        "tagline": "Prime, gateway, sidecar",
        "owner_role": "dev_game",
    },
}


def role_aliases() -> dict[str, dict[str, str]]:
    raw = os.environ.get("LBG_TEAM_ROLE_ALIASES_JSON", "").strip()
    if not raw:
        return dict(DEFAULT_ROLE_ALIASES)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return dict(DEFAULT_ROLE_ALIASES)
        merged = dict(DEFAULT_ROLE_ALIASES)
        for role, meta in data.items():
            if isinstance(role, str) and isinstance(meta, dict):
                merged[role] = {**merged.get(role, {}), **{k: str(v) for k, v in meta.items() if isinstance(v, str)}}
        return merged
    except json.JSONDecodeError:
        return dict(DEFAULT_ROLE_ALIASES)


def role_display(role: str) -> dict[str, str]:
    meta = role_aliases().get(role, {})
    alias = meta.get("alias") or role
    title = meta.get("title") or role
    tagline = meta.get("tagline", "")
    return {"role": role, "alias": alias, "title": title, "tagline": tagline, "label": f"{alias} ({role})"}


def enrich_task_view(data: dict[str, object]) -> dict[str, object]:
    role = str(data.get("role") or "")
    ctx = data.get("context") if isinstance(data.get("context"), dict) else {}
    sub = str(ctx.get("subproject") or "")
    if ctx.get("infographiste_ia") and not sub:
        sub = "infographiste_ia"
    if sub and sub in SUBPROJECT_PERSONAS:
        persona = SUBPROJECT_PERSONAS[sub]
        alias = persona.get("alias") or role
        title = persona.get("title") or role
        out = dict(data)
        out["role_alias"] = alias
        out["role_title"] = title
        out["role_label"] = f"{alias} ({sub})"
        out["subproject_id"] = sub
        return out
    disp = role_display(role)
    out = dict(data)
    out["role_alias"] = disp["alias"]
    out["role_title"] = disp["title"]
    out["role_label"] = disp["label"]
    return out
