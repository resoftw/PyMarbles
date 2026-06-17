import pygame

class Camera:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        # Camera center in world coordinates
        self.x = 0.0
        self.y = 0.0
        # Zoom factor (pixels per world unit)
        # 1.0 means 1 world unit = 1 pixel
        # Standard: say 50.0 pixels per world unit is a good starting point
        self.zoom = 50.0
        self.min_zoom = 5.0
        self.max_zoom = 500.0

    def world_to_screen(self, pos):
        """Convert world coordinates (wx, wy) to screen coordinates (sx, sy)."""
        wx, wy = pos
        # Pymunk's Y axis points UP by default.
        # Screen Y axis points DOWN.
        # Let's align world coords such that Y points up:
        # Screen X = Center X + (World X - Cam X) * Zoom
        # Screen Y = Center Y - (World Y - Cam Y) * Zoom
        sx = int(self.screen_width / 2.0 + (wx - self.x) * self.zoom)
        sy = int(self.screen_height / 2.0 - (wy - self.y) * self.zoom)
        return sx, sy

    def screen_to_world(self, pos):
        """Convert screen coordinates (sx, sy) to world coordinates (wx, wy)."""
        sx, sy = pos
        wx = self.x + (sx - self.screen_width / 2.0) / self.zoom
        wy = self.y - (sy - self.screen_height / 2.0) / self.zoom
        return wx, wy

    def pan(self, dx, dy):
        """Pan camera by pixel offsets dx, dy."""
        # Convert pixel movement to world coordinates
        self.x -= dx / self.zoom
        self.y += dy / self.zoom  # Inverted since screen Y is down

    def zoom_at(self, screen_pos, factor):
        """Zoom in/out keeping the world point under screen_pos stationary."""
        # Get the world coordinate under the cursor
        wx, wy = self.screen_to_world(screen_pos)
        
        # Apply zoom limit
        new_zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        self.zoom = new_zoom
        
        # Adjust camera center so that the same world point remains under the screen position
        # screen_x = Center X + (wx - new_x) * new_zoom  =>
        # (screen_x - Center X) / new_zoom = wx - new_x  =>
        # new_x = wx - (screen_x - Center X) / new_zoom
        self.x = wx - (screen_pos[0] - self.screen_width / 2.0) / self.zoom
        self.y = wy + (screen_pos[1] - self.screen_height / 2.0) / self.zoom

    def follow(self, target_pos, lerp_speed=0.1):
        """Smoothly interpolate camera center towards target_pos."""
        tx, ty = target_pos
        self.x += (tx - self.x) * lerp_speed
        self.y += (ty - self.y) * lerp_speed
