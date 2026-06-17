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

p = PhysicsManager()
p.add_wall((-3, 0), (3, 0))

cam = {
    "render_frame": {
        "pos": (1.0, 2.0),
        "height": 12.0,
        "angle": 0.3,
        "format": "9:16",
        "keyframes": [{"t": 0, "pos": (0, 0), "angle": 0, "height": 10, "interp": "smooth"}]
    },
    "seq_len": 500,
    "seed": 123
}

path = os.path.join(tempfile.gettempdir(), "pm_cam_test.json")
MapManager.save_map(p, path, camera=cam)

p2 = PhysicsManager()
loaded = MapManager.load_map(p2, path)

assert loaded is not None and loaded != False
assert loaded["seq_len"] == 500 and loaded["seed"] == 123
assert loaded["render_frame"]["format"] == "9:16"
assert len(loaded["render_frame"]["keyframes"]) == 1

os.remove(path)
print("OK")
