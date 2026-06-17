import pygame
import math

class UITheme:
    BG_DARK = (15, 17, 23, 220)       # Glassmorphism panel background
    BG_DARK_SOLID = (15, 17, 23)      # Base background
    BORDER = (45, 55, 72)             # Subtle borders
    ACCENT_CYAN = (0, 255, 240)       # Selection / Active borders
    ACCENT_MAGENTA = (255, 0, 128)    # Accent highlighting
    TEXT_LIGHT = (247, 250, 252)      # Main text
    TEXT_MUTED = (160, 174, 192)      # Secondary text
    BTN_NORMAL = (35, 41, 55)
    BTN_HOVER = (49, 58, 77)
    BTN_ACTIVE = (0, 255, 240)
    FONT_NAME = "Arial"               # System font

class Button:
    def __init__(self, x, y, width, height, text, icon_name=None, tooltip=None, action_callback=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.icon_name = icon_name
        self.tooltip = tooltip
        self.action_callback = action_callback
        self.hovered = False
        self.selected = False
        self.font = None # Will load in draw

    def draw(self, surface, font):
        self.font = font
        # Hover check
        mouse_pos = pygame.mouse.get_pos()
        self.hovered = self.rect.collidepoint(mouse_pos)
        
        # Color based on state
        if self.selected:
            bg_color = UITheme.ACCENT_CYAN
            text_color = (0, 0, 0)
            border_color = UITheme.TEXT_LIGHT
        elif self.hovered:
            bg_color = UITheme.BTN_HOVER
            text_color = UITheme.TEXT_LIGHT
            border_color = UITheme.ACCENT_CYAN
        else:
            bg_color = UITheme.BTN_NORMAL
            text_color = UITheme.TEXT_LIGHT
            border_color = UITheme.BORDER
            
        # Draw rounded button body
        pygame.draw.rect(surface, bg_color, self.rect, border_radius=6)
        pygame.draw.rect(surface, border_color, self.rect, width=1, border_radius=6)
        
        # Render text
        text_surf = font.render(self.text, True, text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)
        
        # Tooltip drawing happens at the end of screen render to overlay everything
        if self.hovered and self.tooltip:
            return self.tooltip
        return None

    def check_click(self, mouse_pos):
        if self.rect.collidepoint(mouse_pos):
            if self.action_callback:
                self.action_callback()
            return True
        return False

class Slider:
    def __init__(self, x, y, width, min_val, max_val, initial_val, label="", format_str="{:.2f}"):
        self.rect = pygame.Rect(x, y, width, 16)
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.label = label
        self.format_str = format_str
        self.handle_rect = pygame.Rect(x, y, 16, 16)
        self.dragging = False
        self._update_handle_pos()

    def _update_handle_pos(self):
        # Calculate X position of handle based on value
        val_range = self.max_val - self.min_val
        if val_range == 0:
            pct = 0
        else:
            pct = (self.value - self.min_val) / val_range
        self.handle_rect.x = self.rect.x + pct * (self.rect.width - self.handle_rect.width)
        self.handle_rect.y = self.rect.y

    def draw(self, surface, font):
        # Draw Label
        label_surf = font.render(f"{self.label}: {self.format_str.format(self.value)}", True, UITheme.TEXT_LIGHT)
        surface.blit(label_surf, (self.rect.x, self.rect.y - 18))
        
        # Draw track
        track_rect = pygame.Rect(self.rect.x, self.rect.y + 6, self.rect.width, 4)
        pygame.draw.rect(surface, UITheme.BORDER, track_rect, border_radius=2)
        
        # Hover check
        mouse_pos = pygame.mouse.get_pos()
        hovered = self.handle_rect.collidepoint(mouse_pos) or self.dragging
        
        # Draw handle
        handle_color = UITheme.ACCENT_CYAN if hovered else UITheme.TEXT_MUTED
        pygame.draw.circle(surface, handle_color, self.handle_rect.center, 8)
        pygame.draw.circle(surface, UITheme.BG_DARK_SOLID, self.handle_rect.center, 4)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.handle_rect.collidepoint(event.pos):
                self.dragging = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                mx, my = event.pos
                # Clamp mx to track
                track_min_x = self.rect.x + self.handle_rect.width / 2.0
                track_max_x = self.rect.x + self.rect.width - self.handle_rect.width / 2.0
                mx = max(track_min_x, min(track_max_x, mx))
                
                # Calculate percentage and new value
                pct = (mx - track_min_x) / (track_max_x - track_min_x) if track_max_x != track_min_x else 0
                self.value = self.min_val + pct * (self.max_val - self.min_val)
                self._update_handle_pos()
                return True
        return False

class Tooltip:
    @staticmethod
    def draw(surface, text, pos, font):
        text_surf = font.render(text, True, UITheme.BG_DARK_SOLID)
        padding = 8
        width = text_surf.get_width() + padding * 2
        height = text_surf.get_height() + padding * 2
        
        # Offset slightly from cursor
        x = pos[0] + 15
        y = pos[1] + 15
        
        # Keep inside screen bounds
        scr_width, scr_height = surface.get_size()
        if x + width > scr_width:
            x = pos[0] - width - 5
        if y + height > scr_height:
            y = pos[1] - height - 5
            
        rect = pygame.Rect(x, y, width, height)
        
        # Draw background and border
        pygame.draw.rect(surface, UITheme.ACCENT_CYAN, rect, border_radius=4)
        pygame.draw.rect(surface, UITheme.TEXT_LIGHT, rect, width=1, border_radius=4)
        
        surface.blit(text_surf, (x + padding, y + padding))

def draw_neon_line(surface, p1, p2, color, thickness, camera=None, glow_surf=None):
    """Draws a beautiful glowing line (simulates neon)."""
    # Convert points using camera if provided
    if camera:
        p1_scr = camera.world_to_screen(p1)
        p2_scr = camera.world_to_screen(p2)
    else:
        p1_scr = p1
        p2_scr = p2
        
    # Extract RGB components in case RGBA was passed
    rgb = color[:3]
        
    # Glow effect: draw wider lines with alpha on the shared glow_surf
    if glow_surf is not None:
        for w in [thickness * 3.5, thickness * 2.0]:
            pygame.draw.line(glow_surf, (*rgb, 45), p1_scr, p2_scr, int(w))
    else:
        # Fallback if no shared surface is provided (slow)
        temp_glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for w in [thickness * 3.5, thickness * 2.0]:
            pygame.draw.line(temp_glow, (*rgb, 45), p1_scr, p2_scr, int(w))
        surface.blit(temp_glow, (0, 0))
    
    # Sharp inner line
    pygame.draw.line(surface, color, p1_scr, p2_scr, int(thickness))

def draw_neon_circle(surface, center, radius, color, width=0, camera=None, glow_surf=None):
    """Draws a beautiful glowing circle."""
    if camera:
        center_scr = camera.world_to_screen(center)
        radius_scr = int(radius * camera.zoom)
    else:
        center_scr = center
        radius_scr = int(radius)
        
    # Extract RGB components in case RGBA was passed
    rgb = color[:3]
        
    # Glow effect
    if radius_scr > 0:
        if glow_surf is not None:
            # Outer soft glow directly on shared glow_surf
            pygame.draw.circle(glow_surf, (*rgb, 30), center_scr, radius_scr + 4, width=width + 6 if width > 0 else 0)
            pygame.draw.circle(glow_surf, (*rgb, 60), center_scr, radius_scr + 2, width=width + 3 if width > 0 else 0)
        else:
            # Fallback if no shared surface is provided (slow)
            temp_glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            pygame.draw.circle(temp_glow, (*rgb, 30), center_scr, radius_scr + 4, width=width + 6 if width > 0 else 0)
            pygame.draw.circle(temp_glow, (*rgb, 60), center_scr, radius_scr + 2, width=width + 3 if width > 0 else 0)
            surface.blit(temp_glow, (0, 0))
        
        # Inner sharp circle
        pygame.draw.circle(surface, color, center_scr, radius_scr, width=width)
