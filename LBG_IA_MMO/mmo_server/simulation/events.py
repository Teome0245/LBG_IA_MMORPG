import random
import uuid
import logging
from world.state import WorldState
from entities.event import Event

logger = logging.getLogger(__name__)

class EventEngine:
    """Moteur gérant l'apparition aléatoire et la résolution des événements dans le monde."""
    def __init__(self, tick_interval_s: float = 10.0, spawn_chance: float = 0.02) -> None:
        self.tick_interval_s = tick_interval_s
        self.spawn_chance = spawn_chance
        self._accumulator = 0.0

    def step(self, dt_s: float, world: WorldState) -> None:
        self._accumulator += dt_s
        if self._accumulator >= self.tick_interval_s:
            self._apply_event_tick(world)
            self._accumulator = 0.0

    def _apply_event_tick(self, world: WorldState) -> None:
        # 1. Résolution des événements actifs
        events_to_remove = []
        for eid, evt in world.active_events.items():
            if not evt.active:
                events_to_remove.append(eid)
                continue
                
            # Compter les gardes sur place
            guards_on_site = 0
            for npc in world.npcs.values():
                if npc.role == "guard" and npc.situation.get("location") == evt.location_id:
                    guards_on_site += 1
            
            # Si assez de gardes et pas de résolution en cours, démarrer la résolution
            if guards_on_site >= evt.guards_needed and evt.resolution_start_time is None:
                logger.info(f"Événement {eid} : La Garde est sur place, début de résolution.")
                evt.resolution_start_time = world.now_s
            
            # Si résolution en cours depuis 300s (5min simulées), terminer l'événement
            if evt.resolution_start_time is not None:
                if world.now_s - evt.resolution_start_time >= 300:
                    logger.info(f"Événement {eid} résolu.")
                    evt.active = False
                    events_to_remove.append(eid)
        
        for eid in events_to_remove:
            world.active_events.pop(eid, None)
            
        # 2. Génération de nouveaux événements (si aucun crime actif)
        has_crime = any(e.type == "crime" for e in world.active_events.values())
        if not has_crime and random.random() < self.spawn_chance:
            self._spawn_crime(world)
            
    def _spawn_crime(self, world: WorldState) -> None:
        # Lieux propices au crime
        candidates = ["marché", "auberge_pomme_rouge", "quartier_riche"]
        loc = random.choice(candidates)
        eid = f"evt_{uuid.uuid4().hex[:8]}"
        evt = Event(
            id=eid,
            type="crime",
            location_id=loc,
            start_time=world.now_s,
            guards_needed=2
        )
        world.active_events[eid] = evt
        logger.warning(f"NOUVEL ÉVÉNEMENT: Un crime (ID: {eid}) a éclaté au lieu: {loc} !")
