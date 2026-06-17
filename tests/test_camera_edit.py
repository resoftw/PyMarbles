import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
pygame.display.init()
pygame.display.set_mode((800, 600))

from camera import Camera
from physics_manager import PhysicsManager
from editor import Editor

physics = PhysicsManager()
camera = Camera(800, 600)
camera.x, camera.y = 0.0, 0.0
editor = Editor(physics, camera)

editor.render_frame = {"pos": (0.0, 0.0), "angle": 0.0, "height": 10.0,
                       "format": "16:9", "keyframes": []}
editor.selected_entity = ("render_frame", editor.render_frame)
editor.active_tool = "select"

# The center handle sits at world (0,0) = the frame centre.
assert editor.get_handle_under_mouse((0.0, 0.0)) == "center", \
    editor.get_handle_under_mouse((0.0, 0.0))

# Simulate a center-drag exactly as CAMERA-mode mouse routing does: grab the
# handle at the frame's screen position, then move the cursor.
start_screen = camera.world_to_screen((0.0, 0.0))
editor.handle_mouse_down(start_screen, 1)
assert editor.active_handle == "center", editor.active_handle

before = editor.render_frame["pos"]
end_screen = (start_screen[0] + 120, start_screen[1] + 60)
editor.handle_mouse_move(end_screen)
after = editor.render_frame["pos"]
assert after != before, (before, after)

editor.handle_mouse_up(end_screen, 1)
assert editor.active_handle is None

print("OK")
