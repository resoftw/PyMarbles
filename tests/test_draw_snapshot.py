import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame; pygame.init(); pygame.display.set_mode((64, 64))
from physics_manager import PhysicsManager
from camera import Camera
from simulation import Simulation
from sim_cache import SimCache, capture_snapshot, draw_snapshot

p = PhysicsManager(); p.add_wall((-5, 0), (5, -2)); p.add_spawner((0, 5), rate=0.1, count=5); p.add_escalator((-4, 4), (4, 6))
sim = Simulation(p, Camera(640, 480), None); cache = SimCache(20, 1)
sim.start(seed=1)
for _ in range(20):
    sim.step_one_frame(); cache.append(capture_snapshot(p), p)
cam = Camera(320, 240)
surf = pygame.Surface((320, 240)); glow = pygame.Surface((320, 240), pygame.SRCALPHA)
glow.fill((0, 0, 0, 0))
draw_snapshot(surf, glow, cam, p, cache.frames[19], cache.marble_table, sim_time=20/60.0)
# A marble should have been drawn somewhere (non-background pixel exists)
arr = pygame.surfarray.array3d(surf)
assert arr.sum() > 0, "nothing drawn"
print("OK")
