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
            description="Allowlisted DevOps probe (HTTP GET healthz, optional log tail)",
        ),
        CapabilitySpec(name="unknown", routed_to="agent.fallback", description="Fallback handler"),
    ]
)
