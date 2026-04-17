import time

from world.state import WorldState


class SimulationLoop:
    def __init__(self, world: WorldState, tick_hz: float) -> None:
        self._world = world
        self._tick_s = 1.0 / tick_hz

    @property
    def tick_interval_s(self) -> float:
        """Intervalle cible entre deux ticks (sommeil dans la boucle temps réel)."""
        return self._tick_s

    def tick(self, dt_s: float) -> None:
        self._world.now_s += dt_s
        for npc in self._world.npcs.values():
            npc.gauges.step(dt_s)

    def run_forever(self) -> None:
        last = time.time()
        while True:
            now = time.time()
            dt = now - last
            last = now
            self.tick(dt)
            time.sleep(self._tick_s)

