"""LBG Studios Agents (LBG_SA) — partitions, registre modules, mémoire namespacée (phase 0).

Ancien nom de code : Fable5.
"""

from lbg_sa.memory_store import LbgSaMemoryStore, lbg_sa_memory_enabled, memory_root
from lbg_sa.module_registry import LbgSaModule, get_module, list_modules

__all__ = [
    "LbgSaMemoryStore",
    "LbgSaModule",
    "get_module",
    "lbg_sa_memory_enabled",
    "list_modules",
    "memory_root",
]
