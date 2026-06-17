import os, tempfile
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()
pygame.display.set_mode((64, 64))

from physics_manager import PhysicsManager
from map_manager import MapManager

# Guards FIX 1's data path: a saved camera seed must round-trip through load_map.
p = PhysicsManager()
p.add_wall((-3, 0), (3, 0))

cam = {
    "render_frame": {
        "pos": (0.0, 0.0),
        "height": 10.0,
        "angle": 0.0,
        "format": "16:9",
        "keyframes": [{"t": 0, "pos": (0, 0), "angle": 0, "height": 10, "interp": "smooth"}]
    },
    "seq_len": 250,
    "seed": 4242
}

path = os.path.join(tempfile.gettempdir(), "pm_seed_roundtrip.json")
MapManager.save_map(p, path, camera=cam)

p2 = PhysicsManager()
loaded = MapManager.load_map(p2, path)

assert loaded is not None and loaded != False
assert loaded["seed"] == 4242, f"expected seed 4242, got {loaded.get('seed')}"

os.remove(path)
print("OK")
