# tests/test_step_one.py
import os
import sys
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pygame; pygame.init(); pygame.display.set_mode((64, 64))
from physics_manager import PhysicsManager
from camera import Camera
from simulation import Simulation

p = PhysicsManager(); p.add_spawner((0, 5), rate=0.1, count=5)
sim = Simulation(p, Camera(640, 480), None)
sim.start(seed=42)
for _ in range(60):
    sim.step_one_frame()
assert abs(sim.sim_time - 1.0) < 1e-6, sim.sim_time
print("OK")
