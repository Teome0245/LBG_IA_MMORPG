"""Registry unique partagé entre le routage d’intentions et l’introspection."""

from capabilities.spec import CapabilityConstraint, CapabilitySpec
from registry.in_memory import InMemoryCapabilityRegistry


def _object_schema(properties: dict[str, object], required: list[str] | None = None) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": True,
    }


capability_registry = InMemoryCapabilityRegistry(
    specs=[
        CapabilitySpec(
            name="npc_dialogue",
            routed_to="agent.dialogue",
            description="Dialogue with NPCs",
            mode="mmo_persona",
            risk_level="medium",
            input_schema=_object_schema(
                {
                    "text": {"type": "string"},
                    "context": _object_schema(
                        {
                            "npc_name": {"type": "string"},
                            "world_npc_id": {"type": "string"},
                            "lyra": {"type": "object"},
                            "session_summary": {"type": "object"},
                        }
                    ),
                },
                required=["text"],
            ),
            output_schema=_object_schema(
                {
                    "reply": {"type": "string"},
                    "lyra": {"type": "object"},
                    "meta": {"type": "object"},
                }
            ),
            preconditions=["Use for MMO/persona dialogue, not for local desktop actions."],
            effects=["May produce a NPC reply and optional world action proposal through the existing dialogue contract."],
            errors=["llm_error", "remote_unavailable", "invalid_action_json"],
            constraints=[
                CapabilityConstraint(
                    name="mmo_context_sanitized",
                    description="MMO context is sanitized before it reaches the dialogue agent.",
                ),
                CapabilityConstraint(
                    name="no_private_desktop_context",
                    description="Must not receive raw local files, mail bodies, tokens, or desktop observations.",
                ),
            ],
            tags=["mmo", "dialogue", "lyra"],
        ),
        CapabilitySpec(
            name="quest_request",
            routed_to="agent.quests",
            description="Quest generation/routing",
            mode="mmo_persona",
            input_schema=_object_schema(
                {
                    "text": {"type": "string"},
                    "context": _object_schema({"quest_state": {"type": "object"}, "world_npc_id": {"type": "string"}}),
                },
                required=["text"],
            ),
            output_schema=_object_schema({"quest": {"type": "object"}, "quest_state": {"type": "object"}}),
            effects=["May propose or advance a quest state."],
            errors=["invalid_quest_state"],
            constraints=[
                CapabilityConstraint(
                    name="server_authority",
                    description="World commits remain validated by the authoritative server.",
                )
            ],
            tags=["mmo", "quest"],
        ),
        CapabilitySpec(
            name="combat_action",
            routed_to="agent.combat",
            description="Combat decision support",
            mode="mmo_persona",
            input_schema=_object_schema(
                {"context": _object_schema({"encounter_state": {"type": "object"}})},
                required=["context"],
            ),
            output_schema=_object_schema({"encounter": {"type": "object"}, "encounter_state": {"type": "object"}}),
            effects=["May suggest or advance a combat encounter state."],
            errors=["invalid_encounter_state"],
            constraints=[
                CapabilityConstraint(
                    name="server_authority",
                    description="Authoritative combat resolution must stay server-side when connected to the MMO.",
                )
            ],
            tags=["mmo", "combat"],
        ),
        CapabilitySpec(
            name="core3_bot_action",
            routed_to="agent.core3",
            description="Joueurs IA Core3 (Lia, Nix, futurs bots) ou PNJ pilotes via sidecar HTTP",
            mode="mmo_persona",
            risk_level="medium",
            action_context_key="core3_action",
            input_schema=_object_schema(
                {
                    "text": {"type": "string"},
                    "context": _object_schema(
                        {
                            "core3_action": _object_schema(
                                {
                                    "kind": {
                                        "type": "string",
                                        "enum": ["npc_think", "player_think", "npc_say"],
                                    },
                                    "npc_id": {"type": "string"},
                                    "pilot_id": {"type": "string"},
                                    "player": {"type": "string"},
                                    "prompt": {"type": "string"},
                                    "enqueue": {"type": "boolean"},
                                },
                                required=["kind"],
                            ),
                            "core3_npc_id": {"type": "string"},
                            "world_npc_id": {"type": "string"},
                            "core3_player_id": {"type": "string"},
                            "core3_player_role": {"type": "string"},
                            "core3_profession_current": {"type": "string"},
                            "core3_profession_dynamic": {"type": "boolean"},
                            "core3_capabilities": {"type": "array", "items": {"type": "string"}},
                            "core3_autonomy": {"type": "boolean"},
                        }
                    ),
                },
                required=["text"],
            ),
            output_schema=_object_schema(
                {
                    "sidecar": {"type": "object"},
                    "line": {"type": "string"},
                    "observation": {"type": "string"},
                }
            ),
            preconditions=["Requires context.core3_action and LBG_CORE3_IA_SIDECAR_URL on the orchestrator host."],
            effects=["May enqueue say/perform/interact/move/npc_say/switch_zone on Core3 via ia_bridge/pending.jsonl."],
            errors=["sidecar_unreachable", "player_offline", "npc_offline", "configuration_error"],
            constraints=[
                CapabilityConstraint(
                    name="tatooine_scope",
                    description="Pont limité à Serveur Prime / zone tatooine (ADR 0007).",
                ),
                CapabilityConstraint(
                    name="lan_sidecar",
                    description="Sidecar must be reachable from the orchestrator network.",
                ),
            ],
            tags=["mmo", "core3", "bridge"],
        ),
        CapabilitySpec(
            name="world_aid",
            routed_to="agent.world",
            description="Deterministic world-side aid commit (gauges + reputation deltas)",
            mode="mmo_persona",
            risk_level="medium",
            action_context_key="world_action",
            input_schema=_object_schema(
                {
                    "context": _object_schema(
                        {
                            "world_npc_id": {"type": "string"},
                            "world_action": _object_schema(
                                {
                                    "kind": {"type": "string", "const": "aid"},
                                    "hunger_delta": {"type": "number"},
                                    "thirst_delta": {"type": "number"},
                                    "fatigue_delta": {"type": "number"},
                                    "reputation_delta": {"type": "integer"},
                                },
                                required=["kind"],
                            ),
                        },
                        required=["world_npc_id", "world_action"],
                    )
                },
                required=["context"],
            ),
            output_schema=_object_schema({"commit": {"type": "object"}, "outcome": {"type": "string"}}),
            preconditions=["Requires context.world_action and context.world_npc_id."],
            effects=["May commit bounded aid/reputation deltas through the world bridge."],
            errors=["invalid_world_action", "commit_rejected", "remote_unavailable"],
            constraints=[
                CapabilityConstraint(
                    name="bounded_deltas",
                    description="Gauge and reputation changes are bounded by the server contract.",
                ),
                CapabilityConstraint(
                    name="authoritative_commit",
                    description="The game server validates and applies the commit.",
                ),
            ],
            tags=["mmo", "world", "commit"],
        ),
        CapabilitySpec(
            name="devops_probe",
            routed_to="agent.devops",
            description="Allowlisted DevOps probe (HTTP GET, log tail, systemd is-active, selfcheck bundle)",
            mode="local_assistant",
            risk_level="high",
            action_context_key="devops_action",
            input_schema=_object_schema(
                {
                    "context": _object_schema(
                        {
                            "devops_action": {"type": "object"},
                            "devops_dry_run": {"type": "boolean"},
                            "devops_approval": {"type": "string"},
                        },
                        required=["devops_action"],
                    )
                },
                required=["context"],
            ),
            output_schema=_object_schema({"result": {"type": "object"}, "outcome": {"type": "string"}}),
            preconditions=["Requires context.devops_action.", "Real execution may require context.devops_approval."],
            effects=["May read allowlisted health endpoints, logs, or service status; restart-like actions stay gated."],
            errors=["approval_required", "not_allowed", "execution_error", "configuration_error"],
            constraints=[
                CapabilityConstraint(
                    name="allowlist_required",
                    description="URLs, log paths and systemd units must match explicit allowlists.",
                ),
                CapabilityConstraint(
                    name="approval_for_real_execution",
                    description="Non dry-run sensitive actions require an approval token.",
                ),
                CapabilityConstraint(
                    name="audit_jsonl",
                    description="Sensitive actions are logged as structured audit events.",
                ),
            ],
            tags=["local_assistant", "infra", "devops", "audit"],
        ),
        CapabilitySpec(
            name="network_inventory",
            routed_to="agent.network",
            description="Inventaire réseau LAN read-only (scan sous-réseau 192.168.0.0/24 + sondes HTTP/TCP + hôtes connus)",
            mode="local_assistant",
            risk_level="low",
            action_context_key=None,
            input_schema=_object_schema(
                {
                    "text": {"type": "string"},
                    "context": _object_schema({}),
                },
                required=["text"],
            ),
            output_schema=_object_schema(
                {
                    "devices": {"type": "array"},
                    "n_devices": {"type": "integer"},
                    "reply": {"type": "string"},
                }
            ),
            preconditions=[],
            effects=["Probes read-only sur les hôtes LAN configurés (instantané T)."],
            errors=["probe_error", "configuration_error"],
            constraints=[
                CapabilityConstraint(
                    name="read_only_probes",
                    description="Aucune modification réseau ; sondes HTTP GET et connect TCP uniquement.",
                ),
            ],
            tags=["local_assistant", "infra", "network", "lan"],
        ),
        CapabilitySpec(
            name="project_pm",
            routed_to="agent.pm",
            description="Chef de projet — brief jalons/risques (stub ou HTTP LBG_AGENT_PM_URL)",
            mode="system",
            risk_level="low",
            action_context_key="project_pm",
            input_schema=_object_schema(
                {
                    "text": {"type": "string"},
                    "context": _object_schema({"pm_focus": {"type": "boolean"}, "project_pm": {"type": "object"}}),
                },
                required=["text"],
            ),
            output_schema=_object_schema({"brief": {"type": "object"}}),
            effects=["Produces a planning brief without changing the repo or infrastructure."],
            errors=["remote_unavailable"],
            constraints=[
                CapabilityConstraint(
                    name="read_only_by_default",
                    description="PM output is advisory; implementation remains a separate action.",
                )
            ],
            tags=["assistant", "planning"],
        ),
        CapabilitySpec(
            name="desktop_control",
            routed_to="agent.desktop",
            description="Desktop tools (hybride) — exécution via agent Windows allowlist (UI/web/mail) derrière approval",
            mode="local_assistant",
            risk_level="high",
            action_context_key="desktop_action",
            input_schema=_object_schema(
                {
                    "context": _object_schema(
                        {
                            "desktop_action": {"type": "object"},
                            "desktop_target": {"type": "string"},
                            "desktop_target_host": {"type": "string"},
                            "desktop_dry_run": {"type": "boolean"},
                            "desktop_approval": {"type": "string"},
                        },
                        required=["desktop_action"],
                    )
                },
                required=["context"],
            ),
            output_schema=_object_schema({"result": {"type": "object"}, "outcome": {"type": "string"}}),
            preconditions=["Requires context.desktop_action.", "Worker URL must be configured for real desktop execution."],
            effects=[
                "May open apps, append text, search the web, preview INBOX mail, observe the screen, or run bounded UI steps.",
            ],
            errors=["feature_disabled", "approval_required", "not_allowed", "configuration_error", "execution_error"],
            constraints=[
                CapabilityConstraint(
                    name="dry_run_default",
                    description="Desktop actions should start in dry-run until explicitly enabled.",
                ),
                CapabilityConstraint(
                    name="allowlists_required",
                    description="Apps, URLs, hosts and file paths must match worker allowlists.",
                ),
                CapabilityConstraint(
                    name="approval_for_real_execution",
                    description="Real execution can require context.desktop_approval.",
                ),
                CapabilityConstraint(
                    name="audit_jsonl",
                    description="The worker writes structured audit events for executed actions.",
                ),
            ],
            tags=["local_assistant", "desktop", "web", "mail", "audit"],
        ),
        CapabilitySpec(
            name="prototype_game",
            routed_to="agent.opengame",
            description="Forge OpenGame expérimentale — génération de prototypes gameplay/UX en sandbox",
            mode="system",
            risk_level="high",
            action_context_key="opengame_action",
            input_schema=_object_schema(
                {
                    "context": _object_schema(
                        {
                            "opengame_action": _object_schema(
                                {
                                    "kind": {"type": "string"},
                                    "project_name": {"type": "string"},
                                    "prompt": {"type": "string"},
                                },
                                required=["kind", "project_name", "prompt"],
                            )
                        },
                        required=["opengame_action"],
                    )
                },
                required=["context"],
            ),
            output_schema=_object_schema({"result": {"type": "object"}, "outcome": {"type": "string"}}),
            preconditions=["Requires context.opengame_action.", "Sandbox directory must be configured for real execution."],
            effects=["May generate a prototype in a sandbox; promotion to the MMO remains manual."],
            errors=["approval_required", "sandbox_error", "execution_error"],
            constraints=[
                CapabilityConstraint(
                    name="sandbox_only",
                    description="Generated prototypes must stay outside the authoritative MMO code path.",
                ),
                CapabilityConstraint(
                    name="manual_promotion",
                    description="No automatic merge into the canonical repo.",
                ),
            ],
            tags=["prototype", "sandbox", "assistant"],
        ),
        CapabilitySpec(
            name="economy_regulate",
            routed_to="agent.economy",
            description="Économie macro Prime — signaux shops JSON, règles seuils, actions proposées (dry-run par défaut)",
            mode="mmo_persona",
            risk_level="medium",
            action_context_key="economy_action",
            input_schema=_object_schema(
                {
                    "text": {"type": "string"},
                    "context": _object_schema(
                        {
                            "economy_action": _object_schema(
                                {
                                    "dry_run": {"type": "boolean"},
                                    "stock_overrides": {"type": "object"},
                                }
                            ),
                            "world_director_dry_run": {"type": "boolean"},
                        }
                    ),
                },
                required=["text"],
            ),
            output_schema=_object_schema(
                {
                    "result": {"type": "object"},
                    "proposed_actions": {"type": "array"},
                    "reply": {"type": "string"},
                }
            ),
            preconditions=["Lecture core3_economy.json + economy_rules_v1.json sur l'orchestrateur."],
            effects=["Propose offer_quest / adjust_price_json ; n'écrit pas le JSON économie sans job approuvé."],
            errors=["configuration_error", "evaluation_error"],
            constraints=[
                CapabilityConstraint(
                    name="dry_run_default",
                    description="LBG_WORLD_DIRECTOR_DRY_RUN=1 par défaut — pas d'écriture fichier économie.",
                ),
                CapabilityConstraint(
                    name="tatooine_scope",
                    description="Signaux cantina / shops Prime uniquement (phase macro v1).",
                ),
            ],
            tags=["mmo", "core3", "economy", "world_director"],
        ),
        CapabilitySpec(
            name="world_direct",
            routed_to="agent.chronicler",
            description="Chroniqueur monde — objectifs faction, hints roster, enqueue npc_think sidecar (dry-run par défaut)",
            mode="mmo_persona",
            risk_level="medium",
            action_context_key="world_direct_action",
            input_schema=_object_schema(
                {
                    "text": {"type": "string"},
                    "context": _object_schema(
                        {
                            "world_direct_action": _object_schema(
                                {
                                    "dry_run": {"type": "boolean"},
                                    "stock_overrides": {"type": "object"},
                                }
                            ),
                            "world_director_dry_run": {"type": "boolean"},
                        }
                    ),
                },
                required=["text"],
            ),
            output_schema=_object_schema(
                {
                    "result": {"type": "object"},
                    "roster_hints": {"type": "array"},
                    "reply": {"type": "string"},
                }
            ),
            preconditions=["faction_goals.json + sidecar Prime pour enqueue réel."],
            effects=["Peut enqueue npc_think borné sur le pilote primary du roster cible."],
            errors=["sidecar_unreachable", "configuration_error"],
            constraints=[
                CapabilityConstraint(
                    name="dry_run_default",
                    description="Pas d'enqueue sidecar tant que dry_run=True.",
                ),
                CapabilityConstraint(
                    name="bounded_enqueue",
                    description="Enqueue uniquement npc_think avec prompt scène — pas de commandes shell.",
                ),
            ],
            tags=["mmo", "core3", "chronicler", "world_director"],
        ),
        CapabilitySpec(
            name="unknown",
            routed_to="agent.fallback",
            description="Fallback handler",
            mode="system",
            protocol="internal",
            input_schema=_object_schema({"text": {"type": "string"}, "context": {"type": "object"}}),
            output_schema=_object_schema({"reply": {"type": "string"}, "lyra": {"type": "object"}}),
            effects=["Returns a safe fallback response or echoes Lyra state when applicable."],
            constraints=[
                CapabilityConstraint(
                    name="no_side_effect",
                    description="Fallback must not execute desktop, infra or world writes.",
                )
            ],
            tags=["fallback", "introspection"],
        ),
    ]
)
