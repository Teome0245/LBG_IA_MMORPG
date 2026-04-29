from world.state import WorldState
from entities.npc import Npc


class SocialEngine:
    """
    Moteur de comportements basique (LOD 2/3) pour les PNJ.
    Évalue les jauges périodiquement et modifie les routines (activité, localisation, objectifs).
    """
    def __init__(self, tick_interval_s: float = 10.0) -> None:
        self.tick_interval_s = tick_interval_s
        self._accumulator = 0.0
        self._patrol_route = ["porte_nord", "muraille_est", "place_d_armes", "muraille_ouest"]

    def step(self, dt_s: float, world: WorldState) -> None:
        self._accumulator += dt_s
        if self._accumulator >= self.tick_interval_s:
            self._apply_social_tick(world)
            self._accumulator = 0.0  # Reset pour éviter les rattrapages violents

    def _apply_social_tick(self, world: WorldState) -> None:
        # 1. Évaluation biologique individuelle
        for npc in world.npcs.values():
            self._evaluate_npc(npc, world)
            
        # 2. Logique collective : La Garde (Relève et Patrouille)
        self._manage_guards(world)

    def _evaluate_npc(self, npc: Npc, world: WorldState) -> None:
        # 1. Sauvegarde des attributs de base (si ce n'est pas déjà fait)
        if "default_location" not in npc.situation:
            npc.situation["default_location"] = npc.situation.get("location", "inconnu")
        if "default_goals" not in npc.situation:
            # On stocke les goals initiaux dans la situation pour pouvoir les restaurer
            npc.situation["default_goals"] = npc.goals.copy()

        g = npc.gauges
        
        # 2. Machine à états biologique (PRIORITÉ 0)
        current_activity = npc.situation.get("activity", "working")

        # Priorité 1 : Sommeil
        if g.fatigue >= 0.8:
            npc.situation["activity"] = "sleeping"
            npc.situation["location"] = npc.situation.get("housing", "inconnu")
            npc.goals = ["Se reposer profondément"]
        # Priorité 2 : Faim / Soif
        elif (g.hunger >= 0.8 or g.thirst >= 0.8) and current_activity != "sleeping":
            tavern = world.get_location_by_tag("tavern")
            npc.situation["activity"] = "eating"
            npc.situation["location"] = tavern.id if tavern else "auberge_pomme_rouge"
            npc.goals = ["Manger et boire à la taverne"]
        # Priorité 3 : Retour à la normale
        else:
            if current_activity == "sleeping" and g.fatigue < 0.2:
                self._restore_normal(npc)
            elif current_activity == "eating" and g.hunger < 0.2 and g.thirst < 0.2:
                self._restore_normal(npc)
            elif current_activity not in ("sleeping", "eating"):
                # Reste dans son activité courante (ex: working, patrolling, etc.)
                pass

        # 3. Application des effets biologiques
        new_activity = npc.situation.get("activity", "working")
        if new_activity == "sleeping":
            g.fatigue = max(0.0, g.fatigue - 0.2)
        elif new_activity == "eating":
            g.hunger = max(0.0, g.hunger - 0.3)
            g.thirst = max(0.0, g.thirst - 0.3)
        elif new_activity in ("working", "patrolling", "guarding", "responding_to_alert"):
            g.fatigue = min(1.0, g.fatigue + 0.05)

    def _restore_normal(self, npc: Npc) -> None:
        npc.situation["activity"] = "working"
        npc.situation["location"] = npc.situation.get("default_location", "inconnu")
        default_goals = npc.situation.get("default_goals", [])
        npc.goals = list(default_goals)

    def _manage_guards(self, world: WorldState) -> None:
        """Logique d'organisation des gardes (Planning + Délégation)."""
        guards = [npc for npc in world.npcs.values() if npc.role == "guard"]
        if not guards:
            return

        # Filtrer ceux qui gèrent des besoins biologiques critiques
        active_guards = [g for g in guards if g.situation.get("activity") not in ("sleeping", "eating")]
        if not active_guards:
            return
            
        # Priorité absolue : Les événements en cours (Crime)
        crime_events = [e for e in world.active_events.values() if e.active and e.type == "crime"]
        if crime_events:
            event = crime_events[0]
            for guard in active_guards:
                guard.situation["activity"] = "responding_to_alert"
                guard.situation["location"] = event.location_id
                guard.goals = ["Intervenir sur l'incident !"]
            return
        
        # Cycle de 6 heures (21600 sec) divisé en 3 quarts de 2 heures (7200 sec)
        shift_idx = int((world.now_s % 21600) / 7200)

        # Assigner les rôles requis: 1 à la porte, 1 en patrouille
        needs = ["guarding", "patrolling"]
        assigned = []

        # Tenter d'assigner par planning fixe (les id terminant par shift_idx ou shift_idx+1)
        for guard in active_guards:
            try:
                # Extraire le numéro du garde (guard_1, guard_2...)
                num = int(guard.id.split("_")[-1])
            except ValueError:
                num = 0
            
            # Un pseudo-planning : Garde 1&2 sur shift 0, Garde 3&4 sur shift 1, Garde 5&1 sur shift 2
            expected_shift = (num - 1) % 3
            if expected_shift == shift_idx and len(assigned) < len(needs):
                assigned.append(guard)

        # Délégation : si on n'a pas assez de gardes (parce qu'ils dorment), on prend les autres dispos
        active_guards.sort(key=lambda x: x.gauges.fatigue) # Les moins fatigués en premier
        for guard in active_guards:
            if len(assigned) >= len(needs):
                break
            if guard not in assigned:
                assigned.append(guard)

        # Relève dynamique : Si le garde en patrouille arrive à la porte nord, ils échangent leurs rôles
        if len(assigned) == 2:
            patrol_guard = assigned[1]
            curr_loc = patrol_guard.situation.get("location")
            if curr_loc in self._patrol_route:
                next_idx = (self._patrol_route.index(curr_loc) + 1) % len(self._patrol_route)
                if self._patrol_route[next_idx] == "porte_nord":
                    # Le patrouilleur prend la porte, le garde de la porte part en patrouille
                    assigned[0], assigned[1] = assigned[1], assigned[0]

        # Mettre à jour l'état des gardes
        for guard in active_guards:
            if guard in assigned:
                task = needs[assigned.index(guard)]
                if task == "guarding":
                    guard.situation["activity"] = "guarding"
                    guard.situation["location"] = "porte_nord"
                    guard.goals = ["Garder la porte nord"]
                elif task == "patrolling":
                    guard.situation["activity"] = "patrolling"
                    guard.goals = ["Faire sa ronde sur les murailles"]
                    # Avancer dans la ronde
                    curr_loc = guard.situation.get("location")
                    try:
                        next_idx = (self._patrol_route.index(curr_loc) + 1) % len(self._patrol_route)
                    except ValueError:
                        next_idx = 0
                    guard.situation["location"] = self._patrol_route[next_idx]
            else:
                # Les gardes actifs mais non assignés sont "en attente" à la caserne
                guard.situation["activity"] = "standby"
                guard.situation["location"] = "caserne"
                guard.goals = ["Se reposer à la caserne en attendant le prochain quart"]
