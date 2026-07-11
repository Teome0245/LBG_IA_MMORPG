"""Registre des sous-projets supervisés par l'équipe / orchestrateur."""

from __future__ import annotations

SUBPROJECTS: list[dict[str, object]] = [
    {
        "id": "core3_prime",
        "label": "Core3 Prime (246)",
        "owner_role": "player_ia",
        "paths": ["content/core3/", "tools/core3_ia_sidecar/"],
        "docs": ["docs/core3_prime_runbook.md", "docs/core3_prime_world_systems.md"],
    },
    {
        "id": "client_godot",
        "label": "Client Godot LBG",
        "owner_role": "dev_game",
        "paths": ["lbg_client_godot/", "docs/plan_client_lbg_godot.md"],
        "docs": ["docs/plan_client_lbg_godot.md"],
        "status": "actif",
    },
    {
        "id": "client_swgemu",
        "label": "Client SWGEmu LBG (launchpad)",
        "owner_role": "dev_game",
        "paths": ["docs/client_dual_launchpad.md"],
        "status": "prod_parallèle",
    },
    {
        "id": "equipe_virtuelle",
        "label": "Équipe virtuelle studio",
        "owner_role": "pm",
        "paths": ["orchestrator/team/"],
        "docs": ["docs/architecture_equipe_virtuelle_studio.md", "docs/handoff_equipe_virtuelle_2026-07-10.md"],
    },
    {
        "id": "assistant_pilot",
        "label": "Assistant Core + Pilot",
        "owner_role": "pm",
        "paths": ["pilot_web/", "backend/"],
        "docs": ["docs/assistant_core_plan.md"],
    },
    {
        "id": "infra_ops",
        "label": "Infra LAN / Proxmox",
        "owner_role": "ops",
        "paths": ["infra/scripts/", "infra/systemd/"],
        "docs": ["docs/fusion_env_lan.md"],
    },
    {
        "id": "infographiste_ia",
        "label": "Infographiste IA (assets 3D Godot)",
        "owner_role": "dev_game",
        "paths": [],
        "docs": [],
        "status": "conversation_parallèle",
    },
    {
        "id": "sandbox_python",
        "label": "Bac à sable Python MMO (245)",
        "owner_role": "qa",
        "paths": ["mmo_server/", "mmmorpg_server/", "web_client/"],
        "docs": ["docs/ARCHIVED_mmmorpg_sandbox.md"],
        "status": "gelé",
    },
]


def list_subprojects() -> list[dict[str, object]]:
    return list(SUBPROJECTS)
