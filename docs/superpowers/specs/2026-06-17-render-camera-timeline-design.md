# Render Camera Timeline — Design Spec

Date: 2026-06-17
Project: PyMarbles (2D physics marble race simulator + editor)
Status: Approved direction; pending spec review.

## 1. Goal

Turn the existing render frame into an animatable camera with a Blender-style
timeline: keyframe the frame's pose over a fixed-length sequence, bake the
deterministic simulation into a per-frame cache for free scrubbing, and render
the final HQ video by sampling the camera timeline over the cached frames.

## 2. Modes (2 total)

The app has exactly two modes, toggled by one toolbar button (mirrors the
current SIMULATE/EDIT toggle):

- **EDIT** — build the map with existing tools. The render frame can also be
  placed/transformed here (it is a component). Timeline hidden.
- **CAMERA** — animation/preview workspace. Shows the timeline bar. Live play,
  bake, scrub, and camera keyframing all happen here. The old standalone live
  "SIMULATE" run is absorbed into CAMERA mode.

State added (module-level in `main.py`, or a small `Timeline` holder):
- `mode`: `"edit" | "camera"`
- `seq_len`: total sequence length in frames (set up front, Blender-style)
- `playhead`: current frame index `[0, seq_len)`
- `playing`: bool (advancing during PLAY)

## 3. Sequence length (set up front)

- A control on the timeline bar sets total frames. Default **250**.
- Quick presets: **150 / 250 / 500 / 1000** frames, plus `−`/`+` (±30) nudge.
- `seq_len` is the timeline length AND the render length.
- Changing `seq_len` invalidates the bake cache (dirty).

## 4. Simulation cache (progressive, sequential)

New module `sim_cache.py`. The cache holds per-frame snapshots indexed by frame,
filled **sequentially from frame 0** (physics cannot jump ahead). It tracks
`n_cached` = number of contiguous frames available `[0, n_cached)`.

Two ways the cache fills (both sequential, both append to the frontier):
- **PLAY (live)** — real-time forward simulation from the frontier with **sound**;
  each computed frame is appended to the cache as it goes. This is the
  interactive / "temporary" cache (à la Blender's memory cache while playing).
- **BAKE** — runs from the frontier to `seq_len` as fast as possible (no
  real-time cap), **silent**, with a Blender-style **progress bar**. Completes
  the cache so the whole sequence is scrubbable and render-from-cache is valid.

Determinism already exists: `Simulation.start(seed)` seeds the RNG; substep size
is speed-independent. The seed is stored so a re-run reproduces the same race.

### Audio
- Impact events + rolling envelope are captured (timed by `sim_time`) during the
  fill so the render mux is consistent. Live PLAY also plays them; BAKE is silent
  but still logs them.

### Snapshot per frame
- `marbles`: list of `(id, x, y, angle)`; a separate table maps `id -> (radius, color)`
  (created once; ids are assigned incrementally when a marble spawns).
- `bodies`: transforms `(x, y, angle)` for moving non-marble bodies — dynamic
  boxes, seesaw bars, spinner bodies, elevator platforms (keyed by a stable id).
- Escalator steps / conveyor dots are pure functions of `sim_time` → recomputed
  at draw time, not stored.

### Memory
- ~8–15 MB for a 60s / ~100-marble race. Acceptable.

### Invalidation (cache becomes "dirty", BAKE button shows RE-BAKE)
- Any map edit, `seq_len` change, or seed reroll.

## 5. Timeline bar (CAMERA mode)

Bottom-of-screen bar, shown only in CAMERA mode:
- **Playhead** (scrubbable) + **keyframe markers** + time label `frame / seq_len  (t s)`.
- Transport: **PLAY / PAUSE**, **RESET** (playhead→0).
- **BAKE / RE-BAKE** (RE-BAKE shown when dirty).
- Camera keys: **◆ Add Keyframe**, **🗑 Del Keyframe** (at playhead), **Smooth ↔ Linear** (selected key).
- Sequence length presets + `−`/`+`.
- (Optional) **🎲 reseed** to roll a new race; marks cache dirty.

### Playback behaviour (frontier model)
The cache frontier is `n_cached`. Behaviour depends on where the playhead is:
- **PLAY at the frontier** (`playhead == n_cached < seq_len`): live forward
  simulation **with sound**; appends each new frame to the cache.
- **PLAY inside the cached range** (`playhead < n_cached`): silent playback of
  cached frames (advances the playhead); on reaching the frontier it transitions
  to live simulation (sound resumes).
- **Scrub**: allowed anywhere within `[0, n_cached)`, **silent**. Scrubbing past
  the frontier is not allowed (hint: "Play or Bake to extend").
- **RESET**: playhead → 0 (cache retained; does not re-simulate).

## 6. Camera keyframing

`render_frame` gains:
```
render_frame = {
  pos, height, angle, format,                 # live editable pose == pose at playhead
  'keyframes': [ {t_frame, pos, angle, height, interp:'smooth'|'linear'} ],  # sorted by t_frame
}
```
- The frame's `pos/angle/height` always equal the pose at the current playhead.
- **Add Keyframe**: store current pose at `playhead` (replace if a key already
  exists at that frame). Keyframe time is an integer frame index.
- Editing handles (move/rotate/scale) in CAMERA mode changes the live pose;
  committed via Add Keyframe (no auto-key).
- Scrubbing with ≥1 keyframe sets the live pose = sampled pose at playhead.

### Interpolation
- Between two keyframes, segment parameter `u ∈ [0,1]`.
  - `smooth` (default): smoothstep `u*u*(3-2u)`.
  - `linear`: `u`.
- Applied independently to `pos.x`, `pos.y`, `angle`, `height`.
- Before first / after last keyframe: clamp (hold end pose).
- `<2` keyframes: static frame (current behaviour).

## 7. Render integration (RENDER HQ)

In CAMERA mode, RENDER HQ renders exactly `seq_len` frames (the sequence length
set up front is the definitive render length). The camera holds the last
keyframe pose after the final key (clamp, per §6). STOP can cut early.

- If the cache is **incomplete** (`n_cached < seq_len`), RENDER HQ first completes
  the bake to `seq_len` (silent, progress bar) so the whole sequence is available.
- Then for each frame `f`, draw the cached snapshot through the camera pose
  `sample(keyframes, f)`. No re-simulation during the render pass → fast, and the
  video is guaranteed identical to the preview. Audio muxed from the captured
  event log.
- Rotation handled by the existing render-into-square → rotate-and-crop path.
- Output resolution = the frame's format; 2× supersample. Filename keeps the
  `marble_race_hq_<YYMMDDHHMM>.mp4` timestamp.

## 8. Snapshot drawing

New `draw_scene_from_snapshot(surface, glow, cam, snapshot, sim_time)`:
- Statics (walls, boosters, portals, finish lines, conveyor/escalator guides)
  drawn from `physics` as today.
- Moving objects (marbles, dynamic boxes, seesaws, spinners, elevators) drawn
  from the snapshot transforms.
- Escalator steps / conveyor dots recomputed from `sim_time`.
- Marble trails reconstructed from recent cached frames.
- Live mode keeps using the existing `render_physics_scene` untouched.

## 9. Persistence

- Extend `map_manager.save_map` / `load_map` to read/write a `"camera"` section:
  `{ render_frame (pos, height, angle, format), keyframes, seq_len, seed }`.
- The bake cache itself is NOT saved (it is derived; re-bake after load).
- **Custom filenames**: Save As / Open via a native file dialog using `tkinter`
  (ships with Python; no new dependency). A hidden Tk root is created on demand;
  on failure, fall back to the fixed `maps/map.json`. The existing quick
  SAVE/LOAD buttons remain (default path).

## 10. Files touched

- `sim_cache.py` — new: bake loop, snapshot capture, sample/lookup helpers.
- `editor.py` — render_frame keyframes, interpolation/sample helpers, timeline
  bar drawing + hit-testing, camera-mode handle interaction.
- `main.py` — mode state, timeline transport/scrub events, CAMERA-mode wiring,
  RENDER HQ from cache, file-dialog save/load.
- `map_manager.py` — persist/restore the `"camera"` section.
- `simulation.py` — minor: expose per-frame stepping suitable for baking.
- No changes to physics/audio synthesis algorithms.

## 11. Phased implementation

1. **Phase 1** — `sim_cache.py` bake + snapshot drawing + CAMERA mode shell with
   PLAY/PAUSE/RESET and scrub over the baked cache. (No camera keyframes yet.)
2. **Phase 2** — camera keyframes + interpolation + timeline keyframe UI
   (Add/Del/Smooth-Linear), live-pose-follows-playhead.
3. **Phase 3** — RENDER HQ from cache (+ baked audio); deterministic fallback.
4. **Phase 4** — persistence of the camera section + custom-filename save/load.

Each phase is independently testable (geometry/interp/bake unit-tested headless;
GUI confirmed by the user).

## 12. Out of scope (YAGNI)

- Animating the output format/aspect mid-sequence.
- Custom bezier easing handles (only smooth/linear).
- Multiple cameras / camera switching.
- Saving the bake cache to disk.
- Audio during scrub/preview (only in final render).

## 13. Risks / open points

- Snapshot drawing duplicates a portion of the live draw code; kept minimal and
  separated to avoid disturbing live mode.
- tkinter + pygame focus quirks on some platforms; Windows is the target and
  generally fine. Fallback path retained.
- Rotation sign in rotate-and-crop was reasoned, not yet visually confirmed in
  the GUI (carried over from the existing render frame work).
