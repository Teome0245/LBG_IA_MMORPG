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
        "tagline": "Core3, prototypes OpenGame, build Vulcan",
    },
    "dev_godot": {
        "alias": "Iris",
        "title": "Dev Godot IA",
        "tagline": "Prime Client 2D — UI, cartes, M9 (persona Hermès pour réseau)",
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
    "core3_build": {
        "alias": "Vulcan",
        "title": "Forge Core3",
        "tagline": "Build Antigravity, ZB-0, déploiement Prime",
        "owner_role": "dev_game",
    },
    "godot_iris": {
        "alias": "Iris",
        "title": "Godot 2D — UI & cartes",
        "tagline": "Prime Client, M9, minimap, waypoints, scènes GDScript",
        "owner_role": "dev_godot",
    },
    "godot_hermes": {
        "alias": "Hermès",
        "title": "Godot réseau — SOE & gateway",
        "tagline": "SOE M3/M5, lbg-ws/2, bridges UDP/WebSocket",
        "owner_role": "dev_godot",
    },
    "prime_client_2d": {
        "alias": "Iris",
        "title": "Prime Client 2D",
        "tagline": "Scrapaltai, M9, Godot top-down",
        "owner_role": "dev_godot",
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
    if ctx.get("core3_build") and not sub:
        sub = "core3_build"
    persona = str(ctx.get("godot_dev_persona") or "").lower()
    if persona == "hermes" and not sub:
        sub = "godot_hermes"
    elif (persona == "iris" or ctx.get("dev_godot_focus")) and not sub:
        sub = "godot_iris"
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
