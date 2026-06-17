# Render Camera Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the render frame into a keyframed camera with a Blender-style timeline, backed by a progressive deterministic simulation cache, rendered from cache, and persisted to the map with custom-name save/load.

**Architecture:** A progressive per-frame snapshot cache (`sim_cache.py`) is filled sequentially by live PLAY or by BAKE. A bottom timeline bar (`timeline.py`) drives a new CAMERA mode in `main.py` for play/scrub/keyframe. The render frame gains keyframes; its pose is sampled from the timeline during preview and HQ render (which draws cached snapshots through the camera). Persistence extends `map_manager`; custom filenames use tkinter dialogs.

**Tech Stack:** Python 3.11, pygame 2.6, pymunk, numpy, OpenCV, FFmpeg, tkinter (stdlib, for file dialogs).

## Global Constraints

- No new pip dependencies (tkinter is stdlib).
- Do not change physics or audio synthesis algorithms.
- Live EDIT-mode rendering path (`render_physics_scene`) must remain untouched in behavior.
- Determinism: a run is reproduced by `Simulation.start(seed)`; substep size is speed-independent.
- Default sequence length: **250** frames. Presets: 150 / 250 / 500 / 1000; nudge ±30.
- Tests are plain assert scripts run headless: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/<name>.py`. They must print a final `OK` line and exit 0.
- Output resolution = render frame format; 2× supersample. HQ filename: `marble_race_hq_<YYMMDDHHMM>.mp4`.
- Spec: `docs/superpowers/specs/2026-06-17-render-camera-timeline-design.md`.

---

## File Structure

- Create `sim_cache.py` — `SimCache` (snapshot store + frontier + audio events), `capture_snapshot(physics)`, `draw_snapshot(surface, glow, cam, physics, snapshot, sim_time)`.
- Create `camera_anim.py` — keyframe helpers: `add_keyframe`, `delete_keyframe_at`, `sample_camera_pose`, `apply_pose`, `sequence_end_frame`.
- Create `timeline.py` — `TimelineBar` UI widget: draw + hit-test returning action strings; holds button rects.
- Modify `editor.py` — assign incremental marble ids at spawn is in physics; here add nothing structural beyond using `camera_anim` for the selected render_frame (handles already exist).
- Modify `physics_manager.py` — assign `shape.uid` to every created body-bearing entity (marbles, dynamic boxes, seesaw, spinner, elevator) for stable snapshot keys.
- Modify `simulation.py` — expose `step_one_frame()` that advances exactly one render frame (dt) deterministically (extracted from `update`).
- Modify `main.py` — `mode` state, CAMERA-mode event wiring, bake loop, scrub/preview draw, RENDER HQ from cache, tkinter save/load.
- Modify `map_manager.py` — read/write `"camera"` section.

---

## Phase 1 — Simulation cache + snapshot draw + CAMERA mode shell

### Task 1: Stable uids on physics bodies

**Files:**
- Modify: `physics_manager.py` (add `self._uid_counter`, assign `shape.uid` in `add_marble`, `add_box`, `add_seesaw`, `add_spinner`, `add_elevator`)
- Test: `tests/test_uids.py`

**Interfaces:**
- Produces: every dynamic/kinematic shape created by PhysicsManager has a unique integer `shape.uid` (marbles too). `PhysicsManager.__init__` sets `self._uid_counter = 0`; helper `self._next_uid()` returns and increments.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_uids.py
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
```

- [ ] **Step 2: Run it; expect AttributeError (no uid)**
Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_uids.py`
Expected: FAIL (`'Circle' object has no attribute 'uid'`).

- [ ] **Step 3: Implement uids**
In `PhysicsManager.__init__` add near the top:
```python
self._uid_counter = 0
```
Add method:
```python
def _next_uid(self):
    self._uid_counter += 1
    return self._uid_counter
```
In `add_marble`, after `shape.collision_type = self.COLLISION_MARBLE` add `shape.uid = self._next_uid()`.
In `add_box`, after `shape.collision_type = self.COLLISION_BOX` add `shape.uid = self._next_uid()`.
In `add_seesaw`, after `shape.collision_type = self.COLLISION_SEESAW` add `shape.uid = self._next_uid()`.
In `add_spinner`, after the blade shapes are created assign one uid to the spinner body group: add `spinner_data['uid'] = self._next_uid()` to the dict (spinner draws from one body angle).
In `add_elevator`, after `shape.collision_type = self.COLLISION_WALL` add `elev_data['uid'] = self._next_uid()`.

- [ ] **Step 4: Run test; expect OK**
Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_uids.py`
Expected: prints `OK`.

- [ ] **Step 5: Commit**
```bash
git add physics_manager.py tests/test_uids.py
git commit -m "feat: stable uids on physics bodies for snapshot keys"
```

### Task 2: Single-frame stepping in Simulation

**Files:**
- Modify: `simulation.py` (extract `step_one_frame`)
- Test: `tests/test_step_one.py`

**Interfaces:**
- Produces: `Simulation.step_one_frame()` advances exactly `self.dt` of sim time using 4 substeps at `self.dt/4`, runs spawners, updates trails/leaderboard, ignores `speed_multiplier`. Returns nothing. `update()` keeps current real-time behavior by calling the shared substep code.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_step_one.py
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
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
```

- [ ] **Step 2: Run it; expect AttributeError**
Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_step_one.py`
Expected: FAIL (`'Simulation' object has no attribute 'step_one_frame'`).

- [ ] **Step 3: Implement**
Add to `Simulation`:
```python
def step_one_frame(self):
    """Advances exactly one render frame (dt) using 4 substeps, deterministically.
    Independent of speed_multiplier; used by baking and offline render."""
    substeps = 4
    step_size = self.dt / substeps
    from sound_manager import SoundManager
    sound_mgr = SoundManager.get_instance()
    for _ in range(substeps):
        self.physics.update_spawners(self.sim_time)
        if sound_mgr.recording:
            sound_mgr.current_time = self.sim_time
        self.physics.step(step_size)
        self.sim_time += step_size
    self._update_marble_trails()
    sound_mgr.update_rolling(self.physics.marbles)
    self._update_leaderboard()
```

- [ ] **Step 4: Run test; expect OK**
Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_step_one.py`
Expected: prints `OK`.

- [ ] **Step 5: Commit**
```bash
git add simulation.py tests/test_step_one.py
git commit -m "feat: deterministic single-frame stepping for baking"
```

### Task 3: SimCache data structure + snapshot capture

**Files:**
- Create: `sim_cache.py`
- Test: `tests/test_sim_cache.py`

**Interfaces:**
- Produces:
  - `class SimCache` with attributes `seq_len:int`, `seed:int|None`, `frames:list[dict]` (snapshots), `marble_table:dict[int,(radius,color)]`, `audio_events:list`, `rolling_env:list`.
  - `SimCache(seq_len, seed)` constructor; `n_cached` property = `len(self.frames)`; `is_complete` = `n_cached >= seq_len`.
  - `capture_snapshot(physics) -> dict` (module function): returns `{'marbles': [(uid,x,y,angle)], 'bodies': {uid:(x,y,angle)}}` and registers new marbles into a passed table via `cache.note_marbles(physics)`.
  - `cache.append(snapshot)` appends and updates marble_table.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_sim_cache.py
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame; pygame.init(); pygame.display.set_mode((64, 64))
from physics_manager import PhysicsManager
from camera import Camera
from simulation import Simulation
from sim_cache import SimCache, capture_snapshot

p = PhysicsManager(); p.add_spawner((0, 5), rate=0.1, count=5)
sim = Simulation(p, Camera(640, 480), None)
cache = SimCache(seq_len=30, seed=7)
sim.start(seed=cache.seed)
for _ in range(30):
    sim.step_one_frame()
    cache.append(capture_snapshot(p), p)
assert cache.n_cached == 30
assert cache.is_complete
snap = cache.frames[20]
assert "marbles" in snap and "bodies" in snap
for (uid, x, y, ang) in snap["marbles"]:
    assert uid in cache.marble_table          # radius+color registered
print("OK")
```

- [ ] **Step 2: Run it; expect ModuleNotFoundError**
Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_sim_cache.py`
Expected: FAIL (`No module named 'sim_cache'`).

- [ ] **Step 3: Implement `sim_cache.py` (data + capture)**
```python
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
```
Note: add `seesaw_data['uid'] = self._next_uid()` in `add_seesaw` (Task 1 covered marbles/box/spinner/elevator; add seesaw uid now if missed).

- [ ] **Step 4: Run test; expect OK**
Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_sim_cache.py`
Expected: prints `OK`.

- [ ] **Step 5: Commit**
```bash
git add sim_cache.py tests/test_sim_cache.py physics_manager.py
git commit -m "feat: SimCache store and per-frame snapshot capture"
```

### Task 4: Draw a scene from a snapshot

**Files:**
- Modify: `sim_cache.py` (add `draw_snapshot`)
- Test: `tests/test_draw_snapshot.py`

**Interfaces:**
- Produces: `draw_snapshot(surface, glow, cam, physics, snapshot, marble_table, sim_time)` — fills background, draws statics from `physics` (walls, boosters, portals, finish, conveyor/escalator guides + time-based step/dot visuals using `sim_time`), then draws marbles + dynamic boxes/seesaws/spinners/elevators from `snapshot` transforms. Mirrors `main.render_physics_scene` visuals but reads moving transforms from the snapshot.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_draw_snapshot.py
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame; pygame.init(); pygame.display.set_mode((64, 64))
from physics_manager import PhysicsManager
from camera import Camera
from simulation import Simulation
from sim_cache import SimCache, capture_snapshot, draw_snapshot

p = PhysicsManager(); p.add_wall((-5, 0), (5, -2)); p.add_spawner((0, 5), rate=0.1, count=5)
sim = Simulation(p, Camera(640, 480), None); cache = SimCache(20, 1)
sim.start(seed=1)
for _ in range(20):
    sim.step_one_frame(); cache.append(capture_snapshot(p), p)
cam = Camera(320, 240)
surf = pygame.Surface((320, 240)); glow = pygame.Surface((320, 240), pygame.SRCALPHA)
glow.fill((0, 0, 0, 0))
draw_snapshot(surf, glow, cam, p, cache.frames[19], cache.marble_table, sim_time=20/60.0)
# A marble should have been drawn somewhere (non-background pixel exists)
arr = pygame.surfarray.array3d(surf)
assert arr.sum() > 0, "nothing drawn"
print("OK")
```

- [ ] **Step 2: Run it; expect ImportError (draw_snapshot)**
Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_draw_snapshot.py`
Expected: FAIL (`cannot import name 'draw_snapshot'`).

- [ ] **Step 3: Implement `draw_snapshot`**
Add to `sim_cache.py`. Reuse the static-drawing portions from `main.render_physics_scene` (walls, boosters, portals, finish, conveyors, escalators guides, spawners) verbatim, but draw marbles and dynamic bodies from the snapshot:
```python
def draw_snapshot(surface, glow, cam, physics, snapshot, marble_table, sim_time):
    surface.fill(UITheme.BG_DARK_SOLID)
    # --- statics (copied from render_physics_scene: portals, finish, boosters,
    #     walls, conveyors w/ time dots, escalators w/ time-stepped treads,
    #     spawners). Use sim_time for conveyor/escalator animation phase. ---
    # (Implementer: copy those blocks from main.render_physics_scene, replacing
    #  simulation.sim_time with the sim_time argument.)

    # Dynamic boxes / seesaws / spinners / elevators from snapshot transforms:
    bodies = snapshot["bodies"]
    for box in physics.boxes:
        if not getattr(box, "is_dynamic", False) or box.uid not in bodies:
            # static boxes are fixed: draw at their own transform
            bx, by, ba = box.body.position.x, box.body.position.y, box.body.angle
        else:
            bx, by, ba = bodies[box.uid]
        _draw_poly_body(surface, glow, cam, box.width, box.height, bx, by, ba, box.color)
    # seesaws, spinners, elevators: same pattern using their stored width/height/length
    # ... (implementer mirrors render_physics_scene shapes, transform from bodies[uid])

    surface.blit(glow, (0, 0))

    # Marbles from snapshot
    for (uid, x, y, ang) in snapshot["marbles"]:
        radius, color = marble_table[uid]
        center = cam.world_to_screen((x, y))
        rad = int(radius * cam.zoom)
        if rad > 0:
            pygame.draw.circle(surface, color, center, rad)
            pygame.draw.circle(surface, (255, 255, 255), center, rad, width=1)
            edge = cam.world_to_screen((x + radius * math.cos(ang), y + radius * math.sin(ang)))
            pygame.draw.line(surface, (0, 0, 0), center, edge, 2)


def _draw_poly_body(surface, glow, cam, w, h, cx, cy, angle, color):
    hw, hh = w / 2.0, h / 2.0
    rx, ry = math.cos(angle), math.sin(angle)
    ux, uy = -math.sin(angle), math.cos(angle)
    local = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    world = [(cx + lx * rx + ly * ux, cy + lx * ry + ly * uy) for (lx, ly) in local]
    scr = [cam.world_to_screen(wv) for wv in world]
    pygame.draw.polygon(surface, (*color, 120), scr)
    for i in range(4):
        draw_neon_line(surface, world[i], world[(i + 1) % 4], color, 2, cam, glow_surf=glow)
```
(Implementer copies the static blocks and the seesaw/spinner/elevator shape drawing from `main.render_physics_scene`, substituting transforms from `bodies[uid]`. Trails are reconstructed by the caller in Phase 3 if desired; not required for this test.)

- [ ] **Step 4: Run test; expect OK**
Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_draw_snapshot.py`
Expected: prints `OK`.

- [ ] **Step 5: Commit**
```bash
git add sim_cache.py tests/test_draw_snapshot.py
git commit -m "feat: draw a scene from a cached snapshot"
```

### Task 5: CAMERA mode shell + bake loop + scrub (manual GUI verify)

**Files:**
- Modify: `main.py` (mode state, mode toggle button label, timeline-driven loop branch, bake function, scrub draw)
- Create: `timeline.py` (TimelineBar) — minimal version: playhead + PLAY/PAUSE/RESET/BAKE + seq-len presets; keyframe buttons added in Phase 2.

**Interfaces:**
- Produces:
  - module state in `main.py`: `mode = "edit"`, `seq_len = 250`, `playhead = 0`, `playing = False`, `cache = None` (SimCache), `cache_dirty = True`.
  - `class TimelineBar` in `timeline.py` with `__init__(self, screen_w, screen_h)`, `layout(seq_len)`, `draw(surface, font, playhead, seq_len, n_cached, playing, keyframes=None)`, and `hit(pos) -> str|None` returning one of: `"play"`,`"pause"`,`"reset"`,`"bake"`,`"len_150"`,`"len_250"`,`"len_500"`,`"len_1000"`,`"len_minus"`,`"len_plus"`,`"scrub:<frame>"` (when the track is clicked), or `None`.
  - `bake_to(target_frames)` in `main.py`: from `cache.n_cached` to `target_frames`, calls `simulation.step_one_frame()` + `cache.append(...)` per frame, with a progress overlay (reuse `_draw_saving_overlay` style), silent (`SoundManager.offline=True`, recording on to log events into `cache.audio_events`/`rolling_env`).

- [ ] **Step 1: Implement TimelineBar (no test; pure UI) — write `timeline.py`**
Provide `layout`, `draw` (bar rect along the bottom ~70px tall; track rect; playhead marker; buttons with rects stored on self), and `hit` mapping click positions to action strings. Track click → `f"scrub:{frame}"` where `frame = round((mx - track.x)/track.w * (seq_len-1))` clamped.

- [ ] **Step 2: Wire mode + state into `main.py`**
- Replace the SIMULATE/EDIT button callback to toggle `mode` between `"edit"` and `"camera"` (rename label accordingly). Keep `simulation.running` meaning "physics is being stepped live this frame".
- When entering CAMERA mode: create `cache = SimCache(seq_len, simulation.seed or new_seed)` if dirty; set `playhead=0`, `playing=False`.
- In the main loop, branch: if `mode == "camera"`, draw the timeline bar; handle its `hit` actions (play/pause/reset/bake/len_*/scrub). On `play`, advance: if `playhead < cache.n_cached` → silent cache playback (increment playhead, draw via `draw_snapshot`); else if `cache.n_cached < seq_len` → `simulation.step_one_frame()` + `cache.append` + live sound, `playhead = cache.n_cached`. On `scrub:f` → set `playhead=f` (only if `f < cache.n_cached`).
- Render: in CAMERA mode draw the current frame via `draw_snapshot(screen, glow, camera, physics, cache.get(playhead), cache.marble_table, playhead/60.0)` when cached; if at the live frontier, the live `render_physics_scene` result is already on screen.

- [ ] **Step 3: Implement `bake_to(target)` with progress overlay**
Loop stepping the sim and appending to cache; every few frames draw a progress bar (`done/target`); pump events; allow ESC to stop early (partial cache).

- [ ] **Step 4: Manual GUI verification (checkpoint)**
Run: `python main.py`. Verify: toggle EDIT⇄CAMERA; in CAMERA, PLAY runs the race with sound and fills the cache; PAUSE; scrub the played range (silent) and the marbles jump to that frame; BAKE fills to 250 with a progress bar; after bake, scrub anywhere. Report any errors.

- [ ] **Step 5: Commit**
```bash
git add main.py timeline.py
git commit -m "feat: CAMERA mode with progressive cache, scrub, and bake"
```

---

## Phase 2 — Camera keyframing + interpolation

### Task 6: Keyframe model + interpolation helpers

**Files:**
- Create: `camera_anim.py`
- Test: `tests/test_camera_anim.py`

**Interfaces:**
- Produces (all operate on a `render_frame` dict that has a `"keyframes"` list of `{"t":int, "pos":(x,y), "angle":float, "height":float, "interp":"smooth"|"linear"}`, sorted by `"t"`):
  - `add_keyframe(frame, t)` — snapshot current `frame` pose at integer time `t` (replace if a key exists at `t`); keeps list sorted.
  - `delete_keyframe_at(frame, t)` — removes a key at `t` if present.
  - `sample_camera_pose(frame, t) -> (pos, angle, height)` — interpolated pose; clamps before first/after last; returns the static pose if `<2` keys (or the single key's pose).
  - `apply_pose(frame, pose)` — writes `pos/angle/height` back onto `frame`.
  - `sequence_end_frame(frame) -> int` — `t` of the last keyframe (or 0).

- [ ] **Step 1: Write the failing test**
```python
# tests/test_camera_anim.py
from camera_anim import add_keyframe, sample_camera_pose, delete_keyframe_at, sequence_end_frame

f = {"pos": (0.0, 0.0), "angle": 0.0, "height": 10.0, "format": "16:9", "keyframes": []}
f["pos"] = (0.0, 0.0); f["angle"] = 0.0; f["height"] = 10.0
add_keyframe(f, 0)
f["pos"] = (10.0, 0.0); f["angle"] = 1.0; f["height"] = 20.0
add_keyframe(f, 100)
# midpoint with smooth easing: smoothstep(0.5)=0.5 -> exactly halfway
pos, ang, h = sample_camera_pose(f, 50)
assert abs(pos[0] - 5.0) < 1e-6, pos
assert abs(h - 15.0) < 1e-6, h
# clamp before first / after last
assert sample_camera_pose(f, -10)[0][0] == 0.0
assert sample_camera_pose(f, 999)[0][0] == 10.0
# linear interp at quarter
f["keyframes"][1]["interp"] = "linear"
pos2, _, _ = sample_camera_pose(f, 25)
assert abs(pos2[0] - 2.5) < 1e-6, pos2
assert sequence_end_frame(f) == 100
# replace + delete
add_keyframe(f, 0); assert len(f["keyframes"]) == 2
delete_keyframe_at(f, 100); assert len(f["keyframes"]) == 1
print("OK")
```

- [ ] **Step 2: Run it; expect ModuleNotFoundError**
Run: `python tests/test_camera_anim.py`
Expected: FAIL (`No module named 'camera_anim'`).

- [ ] **Step 3: Implement `camera_anim.py`**
```python
def _smoothstep(u):
    return u * u * (3.0 - 2.0 * u)


def add_keyframe(frame, t):
    t = int(t)
    kf = {"t": t, "pos": tuple(frame["pos"]), "angle": float(frame["angle"]),
          "height": float(frame["height"]), "interp": "smooth"}
    keys = [k for k in frame.get("keyframes", []) if k["t"] != t]
    keys.append(kf)
    keys.sort(key=lambda k: k["t"])
    frame["keyframes"] = keys


def delete_keyframe_at(frame, t):
    frame["keyframes"] = [k for k in frame.get("keyframes", []) if k["t"] != int(t)]


def sequence_end_frame(frame):
    keys = frame.get("keyframes", [])
    return keys[-1]["t"] if keys else 0


def sample_camera_pose(frame, t):
    keys = frame.get("keyframes", [])
    if not keys:
        return tuple(frame["pos"]), float(frame["angle"]), float(frame["height"])
    if len(keys) == 1 or t <= keys[0]["t"]:
        k = keys[0]; return tuple(k["pos"]), k["angle"], k["height"]
    if t >= keys[-1]["t"]:
        k = keys[-1]; return tuple(k["pos"]), k["angle"], k["height"]
    # find bracketing keys
    for i in range(len(keys) - 1):
        a, b = keys[i], keys[i + 1]
        if a["t"] <= t <= b["t"]:
            span = (b["t"] - a["t"]) or 1
            u = (t - a["t"]) / span
            if b["interp"] == "smooth":
                u = _smoothstep(u)
            pos = (a["pos"][0] + (b["pos"][0] - a["pos"][0]) * u,
                   a["pos"][1] + (b["pos"][1] - a["pos"][1]) * u)
            ang = a["angle"] + (b["angle"] - a["angle"]) * u
            h = a["height"] + (b["height"] - a["height"]) * u
            return pos, ang, h
    k = keys[-1]; return tuple(k["pos"]), k["angle"], k["height"]


def apply_pose(frame, pose):
    pos, angle, height = pose
    frame["pos"] = pos; frame["angle"] = angle; frame["height"] = height
```

- [ ] **Step 4: Run test; expect OK**
Run: `python tests/test_camera_anim.py`
Expected: prints `OK`.

- [ ] **Step 5: Commit**
```bash
git add camera_anim.py tests/test_camera_anim.py
git commit -m "feat: camera keyframe model and smooth/linear interpolation"
```

### Task 7: render_frame gains keyframes; editor + timeline keyframe UI (manual GUI verify)

**Files:**
- Modify: `editor.py` (when creating `render_frame`, add `"keyframes": []`)
- Modify: `timeline.py` (add Add/Del/Smooth-Linear buttons + keyframe markers on track; extend `hit` actions: `"key_add"`,`"key_del"`,`"key_interp"`)
- Modify: `main.py` (wire keyframe actions; on scrub/play set live pose via `apply_pose(rf, sample_camera_pose(rf, playhead))`; selecting a keyframe marker)

**Interfaces:**
- Consumes: `camera_anim.add_keyframe/delete_keyframe_at/sample_camera_pose/apply_pose`.
- Produces: editing the frame in CAMERA mode + "Add Keyframe" stores the pose; scrubbing moves the frame to the interpolated pose.

- [ ] **Step 1: Add `"keyframes": []` to the `render_frame` dict in `editor.handle_mouse_up`** (the renderframe creation block) and in any place a frame is constructed.

- [ ] **Step 2: Extend TimelineBar** with three buttons (Add ◆ / Del 🗑 / interp) and draw keyframe markers at `track.x + k["t"]/(seq_len-1)*track.w`. Extend `hit` to return the new actions and `"selectkey:<t>"` when a marker is clicked.

- [ ] **Step 3: Wire in `main.py`** — on `key_add`: `camera_anim.add_keyframe(rf, playhead)`; on `key_del`: `delete_keyframe_at(rf, playhead)`; on `key_interp`: toggle selected key's interp. On scrub/play with ≥1 keyframe: `apply_pose(rf, sample_camera_pose(rf, playhead))` before drawing so the guide frame shows the interpolated camera.

- [ ] **Step 4: Manual GUI verification (checkpoint)**
Run: `python main.py`. In CAMERA mode after a bake: scrub to frame 0, position/zoom/rotate the frame, Add Keyframe; scrub to 200, move the frame, Add Keyframe; scrub between → the frame eases smoothly between poses. Toggle a key to Linear and confirm the change. Delete a key. Report issues.

- [ ] **Step 5: Commit**
```bash
git add editor.py timeline.py main.py
git commit -m "feat: camera keyframing UI on the timeline"
```

---

## Phase 3 — RENDER HQ from cache

### Task 8: Render the sequence from cache through the camera timeline (manual GUI verify)

**Files:**
- Modify: `main.py` (`run_offline_render` → render from cache + camera timeline)

**Interfaces:**
- Consumes: `cache` (SimCache), `draw_snapshot`, `camera_anim.sample_camera_pose`, existing rotate-and-crop + `video_exporter` + `merge_audio_video`.
- Produces: HQ MP4 of `seq_len` frames; camera pose per frame sampled from the render frame's keyframes; audio muxed from `cache.audio_events`/`rolling_env`.

- [ ] **Step 1: Ensure the cache is complete before render**
At the top of `run_offline_render`, if `cache is None or not cache.is_complete`: call `bake_to(seq_len)` (progress bar). Abort if the user cancels with no frames.

- [ ] **Step 2: Render loop from cache**
For `f in range(seq_len)` (or until STOP): set the render camera (format resolution × SS) centered on `sample_camera_pose(rf, f)`; if rotated, render square + rotate-and-crop; draw via `draw_snapshot(square_or_hi, glow, render_cam, physics, cache.get(f), cache.marble_table, f/60.0)`; smoothscale → write frame; preview overlay every 3 frames. (No live simulation in this loop.)

- [ ] **Step 3: Audio from cache**
Replace the `sm.start_recording()`/live-stepping audio path: write `cache.audio_events` into `SoundManager.recorded_events` and `cache.rolling_env` into `SoundManager.rolling_envelope`, then call `sm.save_wav_recording(temp_audio, seq_len/60.0)`; mux with `merge_audio_video`.

- [ ] **Step 4: Manual GUI verification (checkpoint)**
Run: `python main.py`. Bake, set 2-3 camera keyframes, RENDER HQ. Confirm: progress/preview shows the camera moving; output `exports/marble_race_hq_*.mp4` plays smoothly at the format resolution with audio; the camera motion matches the preview. Report issues (esp. rotation direction).

- [ ] **Step 5: Commit**
```bash
git add main.py sim_cache.py sound_manager.py
git commit -m "feat: RENDER HQ from cache driven by the camera timeline"
```

---

## Phase 4 — Persistence + custom-name save/load

### Task 9: Persist the camera section in map.json

**Files:**
- Modify: `map_manager.py` (`save_map`, `load_map`)
- Test: `tests/test_camera_persist.py`

**Interfaces:**
- Produces: `save_map(physics, filepath, camera=None)` writes `data["camera"] = camera` (a dict: `{render_frame:{pos,height,angle,format,keyframes}, seq_len, seed}`) when provided. `load_map(physics, filepath)` returns the loaded `camera` dict (or `None`) in addition to its current effect; signature becomes `load_map(physics, filepath) -> dict|None|bool` — return the camera section (or `None`) on success, `False` on failure.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_camera_persist.py
import os, tempfile
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame; pygame.init(); pygame.display.set_mode((64, 64))
from physics_manager import PhysicsManager
from map_manager import MapManager

p = PhysicsManager(); p.add_wall((-3, 0), (3, 0))
cam = {"render_frame": {"pos": (1.0, 2.0), "height": 12.0, "angle": 0.3, "format": "9:16",
       "keyframes": [{"t": 0, "pos": (0, 0), "angle": 0, "height": 10, "interp": "smooth"}]},
       "seq_len": 500, "seed": 123}
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
```

- [ ] **Step 2: Run it; expect TypeError (camera kw) or assertion**
Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_camera_persist.py`
Expected: FAIL.

- [ ] **Step 3: Implement**
- `save_map(physics_manager, filepath, camera=None)`: after building `data`, add `if camera is not None: data["camera"] = camera` before `json.dump`. Convert tuples to lists implicitly (json handles tuples as arrays).
- `load_map`: after successfully applying physics, `return data.get("camera")` instead of the current `True`. Keep returning `False` on exception/missing file. Update existing callers in `main.py` to treat any non-`False` (including `None`) as success.

- [ ] **Step 4: Run test; expect OK**
Run: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python tests/test_camera_persist.py`
Expected: prints `OK`.

- [ ] **Step 5: Commit**
```bash
git add map_manager.py tests/test_camera_persist.py
git commit -m "feat: persist camera/timeline section in map JSON"
```

### Task 10: Custom-name Save As / Open via tkinter (manual GUI verify)

**Files:**
- Modify: `main.py` (`save_map`, `load_map` button callbacks; build `camera` dict from `editor.render_frame` + `seq_len` + `simulation.seed`; restore on load)

**Interfaces:**
- Consumes: `MapManager.save_map(..., camera=...)`, `MapManager.load_map(...) -> camera|None|False`.
- Produces: `_ask_save_path()` and `_ask_open_path()` using `tkinter.filedialog` (hidden root), returning a path or `None` (cancelled). SAVE/LOAD buttons use them; on cancel, do nothing. After load, set `editor.render_frame`, `seq_len`, and mark `cache_dirty=True`.

- [ ] **Step 1: Implement the dialogs**
```python
def _ask_save_path():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk(); root.withdraw()
        path = filedialog.asksaveasfilename(
            initialdir=MAPS_DIR, defaultextension=".json",
            filetypes=[("Marble map", "*.json")])
        root.destroy()
        return path or None
    except Exception as e:
        print(f"File dialog unavailable: {e}")
        return os.path.join(MAPS_DIR, "map.json")
# _ask_open_path mirrors with filedialog.askopenfilename
```

- [ ] **Step 2: Wire SAVE/LOAD callbacks** to build/restore the `camera` dict and call the dialogs. Mark `cache_dirty = True` after load (race may differ).

- [ ] **Step 3: Manual GUI verification (checkpoint)**
Run: `python main.py`. Create a frame + keyframes, SAVE MAP → choose a custom name; restart; LOAD MAP → pick it; confirm frame + keyframes + seq_len restored and a re-bake reproduces the saved race (same seed). Report issues.

- [ ] **Step 4: Commit**
```bash
git add main.py
git commit -m "feat: custom-name save/load with camera timeline via tkinter"
```

---

## Self-Review notes

- Spec coverage: modes (Task 5), seq length (Task 5), progressive cache + bake (Tasks 3/5), snapshot draw (Task 4), keyframes + interp (Tasks 6/7), render from cache (Task 8), persistence + custom names (Tasks 9/10), audio capture (Tasks 5/8). Covered.
- The frontier playback nuances (silent cache playback vs sounded live frontier) are implemented in Task 5 Step 2.
- Determinism reuse: `step_one_frame` (Task 2) is the single deterministic stepping primitive used by bake and (fallback) render.
- Rotation direction risk is carried from prior work; flagged at Task 8 Step 4 for visual confirmation.
