"""Registry unique partagé entre le routage d’intentions et l’introspection."""

from capabilities.spec import CapabilitySpec
from registry.in_memory import InMemoryCapabilityRegistry

capability_registry = InMemoryCapabilityRegistry(
    specs=[
        CapabilitySpec(name="npc_dialogue", routed_to="agent.dialogue", description="Dialogue with NPCs"),
        CapabilitySpec(name="quest_request", routed_to="agent.quests", description="Quest generation/routing"),
        CapabilitySpec(name="combat_action", routed_to="agent.combat", description="Combat decision support"),
        CapabilitySpec(
            name="world_aid",
            routed_to="agent.world",
            description="Deterministic world-side aid commit (gauges + reputation deltas)",
        ),
        CapabilitySpec(
            name="devops_probe",
            routed_to="agent.devops",
            description="Allowlisted DevOps probe (HTTP GET, log tail, systemd is-active, selfcheck bundle)",
        ),
        CapabilitySpec(
            name="project_pm",
            routed_to="agent.pm",
            description="Chef de projet — brief jalons/risques (stub ou HTTP LBG_AGENT_PM_URL)",
        ),
        CapabilitySpec(
            name="desktop_control",
            routed_to="agent.desktop",
            description="Desktop tools (hybride) — exécution via agent Windows allowlist (UI/web/mail) derrière approval",
        ),
        CapabilitySpec(
            name="prototype_game",
            routed_to="agent.opengame",
            description="Forge OpenGame expérimentale — génération de prototypes gameplay/UX en sandbox",
        ),
        CapabilitySpec(name="unknown", routed_to="agent.fallback", description="Fallback handler"),
    ]
)
