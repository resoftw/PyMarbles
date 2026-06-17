import math
import pygame
from ui import UITheme, draw_neon_line, draw_neon_circle


class SimCache:
    """Progressive, sequential per-frame snapshot cache for a baked race."""
    def __init__(self, seq_len, seed):
        self.seq_len = int(seq_len)
        self.seed = seed
        self.frames = []                 # list of snapshot dicts
        self.marble_table = {}           # uid -> (radius, color)
        self.audio_events = []           # captured SoundManager events
        self.rolling_env = []            # captured rolling envelope

    @property
    def n_cached(self):
        return len(self.frames)

    @property
    def is_complete(self):
        return self.n_cached >= self.seq_len

    def note_marbles(self, physics):
        for m in physics.marbles:
            if m.uid not in self.marble_table:
                self.marble_table[m.uid] = (m.radius, tuple(m.color))

    def append(self, snapshot, physics):
        self.note_marbles(physics)
        self.frames.append(snapshot)

    def get(self, frame_idx):
        if not self.frames:
            return None
        return self.frames[max(0, min(self.n_cached - 1, int(frame_idx)))]


def capture_snapshot(physics):
    """Captures the transforms of all moving objects for one frame."""
    marbles = [(m.uid, m.body.position.x, m.body.position.y, m.body.angle)
               for m in physics.marbles]
    bodies = {}
    for box in physics.boxes:
        if getattr(box, "is_dynamic", False):
            bodies[box.uid] = (box.body.position.x, box.body.position.y, box.body.angle)
    for ss in physics.seesaws:
        b = ss["body"]; bodies[ss["uid"]] = (b.position.x, b.position.y, b.angle) if "uid" in ss else None
    for sp in physics.spinners:
        b = sp["body"]; bodies[sp["uid"]] = (b.position.x, b.position.y, b.angle)
    for el in physics.elevators:
        b = el["body"]; bodies[el["uid"]] = (b.position.x, b.position.y, b.angle)
    return {"marbles": marbles, "bodies": bodies}
