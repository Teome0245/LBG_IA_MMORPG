import time

from simulation.loop import SimulationLoop
from world.state import WorldState


def main() -> None:
    world = WorldState.bootstrap_default()
    loop = SimulationLoop(world=world, tick_hz=5)
    loop.run_forever()


if __name__ == "__main__":
    main()

