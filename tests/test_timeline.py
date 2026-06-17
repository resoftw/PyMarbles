import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()
pygame.display.set_mode((1280, 720))

from timeline import TimelineBar


def main():
    W, H = 1280, 720
    seq_len = 250
    bar = TimelineBar(W, H)
    bar.layout(seq_len)

    # Each transport / length / keyframe button returns its own action string.
    for name in ("play", "pause", "reset", "bake",
                 "len_150", "len_250", "len_500", "len_1000",
                 "len_minus", "len_plus",
                 "key_add", "key_del", "key_interp"):
        rect = bar.buttons[name]
        assert bar.hit(rect.center) == name, f"button {name} hit mismatch: {bar.hit(rect.center)}"

    # Clicking the far-left edge of the track scrubs to frame 0.
    left = (bar.track.x + 1, bar.track.centery)
    assert bar.hit(left) == "scrub:0", bar.hit(left)

    # Clicking the far-right edge scrubs to the last frame (seq_len - 1).
    right = (bar.track.right - 1, bar.track.centery)
    assert bar.hit(right) == f"scrub:{seq_len - 1}", bar.hit(right)

    # Clicking a known mid-track position matches the documented formula:
    # frame = round((mx - track.x) / track.w * (seq_len - 1)).
    mx = bar.track.x + bar.track.w // 2
    expected = round((mx - bar.track.x) / float(bar.track.w) * (seq_len - 1))
    assert bar.hit((mx, bar.track.centery)) == f"scrub:{expected}", bar.hit((mx, bar.track.centery))

    # A click outside bar/track/buttons returns None.
    assert bar.hit((W // 2, 50)) is None

    # draw() runs without error on a real surface.
    surface = pygame.Surface((W, H))
    font = pygame.font.SysFont("Arial", 13)
    bar.draw(surface, font, playhead=42, seq_len=seq_len, n_cached=100, playing=True)

    # draw() also runs with a non-empty keyframes list (one of which is on the playhead).
    keyframes = [
        {"t": 10, "pos": (0, 0), "angle": 0.0, "height": 5.0, "interp": "smooth"},
        {"t": 120, "pos": (1, 1), "angle": 0.5, "height": 6.0, "interp": "linear"},
    ]
    bar.draw(surface, font, playhead=10, seq_len=seq_len, n_cached=100, playing=False,
             keyframes=keyframes)

    print("OK")


if __name__ == "__main__":
    main()
