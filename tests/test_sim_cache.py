import os
import sys
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame; pygame.init(); pygame.display.set_mode((64, 64))
from physics_manager import PhysicsManager
from camera import Camera
from simulation import Simulation
from sim_cache import SimCache, capture_snapshot

p = PhysicsManager(); p.add_spawner((0, 5), rate=0.1, count=5)
sim = Simulation(p, Camera(640, 480), None)
cache = SimCache(seq_len=30, seed=7)
sim.start(seed=cache.seed)
for _ in range(30):
    sim.step_one_frame()
    cache.append(capture_snapshot(p), p)
assert cache.n_cached == 30
assert cache.is_complete
snap = cache.frames[20]
assert "marbles" in snap and "bodies" in snap
for (uid, x, y, ang) in snap["marbles"]:
    assert uid in cache.marble_table          # radius+color registered
print("OK")
