import pygame
from ui import UITheme


class TimelineBar:
    """Bottom timeline bar for CAMERA mode: playhead scrubbing, transport
    (play/pause/reset/bake), and sequence-length presets.

    Keyframe markers/buttons are planned for a later phase; the ``keyframes``
    argument is accepted now and ignored.
    """

    BAR_HEIGHT = 70

    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.bar = pygame.Rect(0, 0, 0, 0)
        self.track = pygame.Rect(0, 0, 0, 0)
        # Action-name -> Rect for hit-testing.
        self.buttons = {}
        self.layout(250)

    def layout(self, seq_len):
        """Compute bar/track/button rects along the bottom ~70px of the screen."""
        self._seq_len = int(seq_len)
        bh = self.BAR_HEIGHT
        self.bar = pygame.Rect(0, self.screen_h - bh, self.screen_w, bh)

        pad = 10
        btn_h = 28
        btn_y = self.bar.y + (bh - btn_h) // 2
        self.buttons = {}

        # Transport buttons on the left.
        x = pad
        for name, label, w in (
            ("play", "PLAY", 60),
            ("pause", "PAUSE", 64),
            ("reset", "RESET", 64),
            ("bake", "BAKE", 60),
        ):
            self.buttons[name] = pygame.Rect(x, btn_y, w, btn_h)
            x += w + 6

        # Length presets + nudge on the right.
        rx = self.screen_w - pad
        right = []
        for name, label, w in (
            ("len_plus", "+30", 42),
            ("len_minus", "-30", 42),
            ("len_1000", "1000", 52),
            ("len_500", "500", 48),
            ("len_250", "250", 48),
            ("len_150", "150", 48),
        ):
            rx -= w
            self.buttons[name] = pygame.Rect(rx, btn_y, w, btn_h)
            rx -= 6
            right.append((name, label))

        # Scrub track fills the gap between the transport buttons and the presets.
        track_x = x + 8
        track_right = rx - 8
        track_w = max(20, track_right - track_x)
        track_h = 14
        track_y = self.bar.y + (bh - track_h) // 2
        self.track = pygame.Rect(track_x, track_y, track_w, track_h)

        # Labels for drawing (name -> text).
        self._labels = {
            "play": "PLAY", "pause": "PAUSE", "reset": "RESET", "bake": "BAKE",
            "len_150": "150", "len_250": "250", "len_500": "500", "len_1000": "1000",
            "len_minus": "-30", "len_plus": "+30",
        }

    def _frame_to_x(self, frame, seq_len):
        if seq_len <= 1:
            return self.track.x
        frac = max(0.0, min(1.0, frame / float(seq_len - 1)))
        return int(self.track.x + frac * self.track.w)

    def draw(self, surface, font, playhead, seq_len, n_cached, playing, keyframes=None):
        # Bar background.
        pygame.draw.rect(surface, UITheme.BG_DARK_SOLID, self.bar)
        pygame.draw.rect(surface, UITheme.BORDER, self.bar, width=1)

        # Track base.
        pygame.draw.rect(surface, (30, 34, 44), self.track, border_radius=4)

        # Cached-range fill [0, n_cached).
        if n_cached > 0 and seq_len > 1:
            fill_w = self._frame_to_x(min(n_cached - 1, seq_len - 1), seq_len) - self.track.x
            fill_w = max(2, fill_w)
            fill_rect = pygame.Rect(self.track.x, self.track.y, fill_w, self.track.h)
            pygame.draw.rect(surface, (38, 90, 110), fill_rect, border_radius=4)

        # Track border.
        pygame.draw.rect(surface, UITheme.BORDER, self.track, width=1, border_radius=4)

        # Playhead marker.
        px = self._frame_to_x(playhead, seq_len)
        pygame.draw.line(surface, UITheme.ACCENT_CYAN,
                         (px, self.track.y - 4), (px, self.track.bottom + 4), 2)
        pygame.draw.circle(surface, UITheme.ACCENT_CYAN, (px, self.track.y - 4), 4)

        # Time label centered over the track.
        label = f"{int(playhead)} / {int(seq_len)}"
        lbl_surf = font.render(label, True, UITheme.TEXT_LIGHT)
        surface.blit(lbl_surf, lbl_surf.get_rect(center=(self.track.centerx, self.track.y - 16)))

        # Buttons.
        mouse = pygame.mouse.get_pos()
        for name, rect in self.buttons.items():
            hovered = rect.collidepoint(mouse)
            # Highlight PLAY/PAUSE to reflect transport state.
            active = (name == "play" and playing) or (name == "pause" and not playing)
            if active:
                bg = (20, 70, 80)
                border = UITheme.ACCENT_CYAN
            elif hovered:
                bg = (40, 46, 58)
                border = UITheme.ACCENT_CYAN
            else:
                bg = (26, 30, 40)
                border = UITheme.BORDER
            pygame.draw.rect(surface, bg, rect, border_radius=5)
            pygame.draw.rect(surface, border, rect, width=1, border_radius=5)
            txt = font.render(self._labels[name], True, UITheme.TEXT_LIGHT)
            surface.blit(txt, txt.get_rect(center=rect.center))

    def hit(self, pos):
        """Map a click position to an action string, or None.

        Returns one of: "play","pause","reset","bake","len_150","len_250",
        "len_500","len_1000","len_minus","len_plus","scrub:<frame>", or None.
        Track clicks use the seq_len from the most recent :meth:`layout` call.
        """
        for name, rect in self.buttons.items():
            if rect.collidepoint(pos):
                return name
        if self.track.collidepoint(pos):
            return self._scrub(pos)
        return None

    def _scrub(self, pos):
        seq_len = getattr(self, "_seq_len", 250)
        mx = pos[0]
        if self.track.w <= 0 or seq_len <= 1:
            return "scrub:0"
        frac = (mx - self.track.x) / float(self.track.w)
        frame = round(frac * (seq_len - 1))
        frame = max(0, min(seq_len - 1, frame))
        return f"scrub:{frame}"
