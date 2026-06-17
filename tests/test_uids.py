import os
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame; pygame.init(); pygame.display.set_mode((64, 64))
from physics_manager import PhysicsManager

p = PhysicsManager()
m1 = p.add_marble((0, 0)); m2 = p.add_marble((1, 0))
b = p.add_box((2, 0), 1, 1, is_dynamic=True)
assert m1.uid != m2.uid, "marble uids must be unique"
assert b.uid not in (m1.uid, m2.uid), "box uid must be unique"
assert isinstance(m1.uid, int)
print("OK")
