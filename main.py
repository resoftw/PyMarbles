import pygame
import sys
import os
import math
import random
import subprocess
import threading
import datetime
from camera import Camera
from physics_manager import PhysicsManager
from map_manager import MapManager
from video_exporter import VideoExporter
from editor import Editor, RENDER_FORMATS, render_frame_size
from simulation import Simulation
from ui import UITheme, Button, Slider, Tooltip, draw_neon_line, draw_neon_circle
from sound_manager import SoundManager
from sim_cache import SimCache, capture_snapshot, draw_snapshot
from timeline import TimelineBar

# Resolve paths relative to this file so the app runs from any working directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
MAPS_DIR = os.path.join(BASE_DIR, "maps")

def _timestamp():
    """Compact YYMMDDHHMM stamp for export filenames, e.g. 2606171530."""
    return datetime.datetime.now().strftime("%y%m%d%H%M")

# Initialize Pygame and Mixer
pygame.init()
pygame.font.init()
SoundManager.get_instance() # Pre-load sounds and initialize mixer

# Set up screen size (Fullscreen by default)
# We can fall back to a window if fullscreen fails
try:
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
except pygame.error:
    screen = pygame.display.set_mode((1280, 720))
    
pygame.display.set_caption("2D Physics Marble Race Simulator & Editor")
width, height = screen.get_size()

# Create game engines
camera = Camera(width, height)
physics = PhysicsManager()
video_exporter = VideoExporter()
editor = Editor(physics, camera)
simulation = Simulation(physics, camera, video_exporter)

# Load default preset initially to populate the board
MapManager.load_preset(physics, "Plinko Race")
camera.x, camera.y = 0.0, 0.0 # reset cam center

# Fonts
font_small = pygame.font.SysFont(UITheme.FONT_NAME, 13)
font_medium = pygame.font.SysFont(UITheme.FONT_NAME, 15)
font_large = pygame.font.SysFont(UITheme.FONT_NAME, 20, bold=True)

# Layout configuration
SIDEBAR_WIDTH = 300
TOOLBAR_HEIGHT = 60

# Camera panning state
panning = False
pan_start_pos = (0, 0)

# Recording settings
is_recording = False
recording_frame_count = 0
export_filepath = os.path.join(EXPORTS_DIR, "marble_race_recording.mp4")

# Seed of the last live run, so RENDER HQ can reproduce that exact race offline
# (length is controlled manually via the STOP button during rendering).
last_take_seed = None

# CAMERA mode state. "edit" = editor + live physics (existing behaviour);
# "camera" = timeline-driven playback backed by a progressive SimCache.
mode = "edit"
seq_len = 250
playhead = 0
playing = False
cache = None              # SimCache for the current race
cache_dirty = True        # set True whenever the map changes; forces a fresh bake/cache
timeline = None           # TimelineBar, built after screen size is known

# Set up UI Buttons in Toolbar
buttons = []
def build_ui():
    buttons.clear()
    
    # 1. State Control (Offset to x=240 to clear left side for brand logo title)
    # Label shows the mode you'll switch TO (mirrors the old SIMULATE/EDIT pattern).
    mode_label = "CAMERA" if mode == "edit" else "EDIT"
    buttons.append(Button(240, 12, 90, 36, mode_label, tooltip="Toggle between Edit and Camera (timeline) mode", action_callback=toggle_mode))
    
    # 2. Map Actions
    buttons.append(Button(338, 12, 70, 36, "CLEAR", tooltip="Clear entire map", action_callback=clear_map))
    buttons.append(Button(416, 12, 110, 36, "RANDOM MAP", tooltip="Generate procedural track", action_callback=generate_random_map))
    
    # 3. Presets Cycled Selector
    buttons.append(Button(534, 12, 110, 36, "PLINKO PRESET", tooltip="Load Plinko preset map", action_callback=lambda: load_preset_map("Plinko Race")))
    buttons.append(Button(652, 12, 110, 36, "LOOP PRESET", tooltip="Load Loop preset map", action_callback=lambda: load_preset_map("Loop-the-Loop & Jump")))
    buttons.append(Button(770, 12, 110, 36, "PORTAL PRESET", tooltip="Load Portal preset map", action_callback=lambda: load_preset_map("Portal Chaos")))
    
    # 4. Save/Load
    buttons.append(Button(888, 12, 80, 36, "SAVE MAP", tooltip="Save track to map.json", action_callback=save_map))
    buttons.append(Button(976, 12, 80, 36, "LOAD MAP", tooltip="Load track from map.json", action_callback=load_map))
    
    # 5. Recorder + HQ offline renderer
    rec_text = "STOP REC" if is_recording else "RECORD MP4"
    buttons.append(Button(1064, 12, 100, 36, rec_text, tooltip="Record real-time video and audio (live preview)", action_callback=toggle_recording))
    buttons.append(Button(1170, 12, 95, 36, "RENDER HQ", tooltip="Offline frame-locked render at 1080p with live preview; stop manually", action_callback=render_hq_take))

    # 6. Grid snap & Follow camera
    snap_text = "SNAP: ON" if editor.grid_snap else "SNAP: OFF"
    buttons.append(Button(1271, 12, 80, 36, snap_text, tooltip="Toggle Grid Snapping", action_callback=toggle_grid_snap))

    cam_text = "CAM: FOLLOW" if simulation.camera_mode == "leader" else "CAM: FREE"
    buttons.append(Button(1357, 12, 100, 36, cam_text, tooltip="Toggle follow leading marble", action_callback=toggle_camera_mode))
    
    # 7. Quit button
    buttons.append(Button(width - 65, 12, 50, 36, "QUIT", tooltip="Exit the application", action_callback=lambda: sys.exit(0)))

def mark_cache_dirty():
    """Any map edit invalidates the baked race so it gets re-simulated."""
    global cache_dirty
    cache_dirty = True

def enter_camera_mode():
    """(Re)seed the sim and create a fresh SimCache when entering CAMERA mode."""
    global cache, cache_dirty, playhead, playing
    if cache is None or cache_dirty:
        # Reseed deterministically and snapshot frame 0 so scrubbing/playback have
        # a starting frame even before any stepping.
        simulation.start(seed=None)
        cache = SimCache(seq_len, simulation.seed)
        cache.append(capture_snapshot(physics), physics)
        cache_dirty = False
    playhead = 0
    playing = False

def toggle_mode():
    """Switch between EDIT and CAMERA (timeline) modes."""
    global mode, playing, is_recording
    if mode == "edit":
        # Leaving edit: stop any live sim/recording first.
        if is_recording:
            stop_realtime_recording()
        if simulation.running:
            simulation.stop()
        editor.save_undo_state()
        mode = "camera"
        enter_camera_mode()
    else:
        # Leaving camera: return to a stopped edit state.
        playing = False
        simulation.stop()
        mode = "edit"
    build_ui()

def toggle_play_state():
    global is_recording, last_take_seed
    if simulation.running:
        if is_recording:
            stop_realtime_recording()
        # Remember this run's seed so RENDER HQ can reproduce the same race
        last_take_seed = simulation.seed
        simulation.stop()
        # Reset cooldowns and active booster lists
        for b in physics.boosters:
            b['active_marbles'].clear()
        for p in physics.portals:
            p['teleport_cooldowns'].clear()
    else:
        # Save undo state before simulation runs in case objects fall
        editor.save_undo_state()
        simulation.start()
    build_ui()

def clear_map():
    global is_recording
    if is_recording:
        stop_realtime_recording()
    editor.save_undo_state()
    physics.clear()
    simulation.sim_time = 0
    editor.selected_entity = None
    mark_cache_dirty()

def generate_random_map():
    global is_recording
    if is_recording:
        stop_realtime_recording()
    editor.save_undo_state()
    MapManager.generate_random_map(physics)
    camera.x, camera.y = 0.0, 0.0
    editor.selected_entity = None
    mark_cache_dirty()

def load_preset_map(name):
    global is_recording
    if is_recording:
        stop_realtime_recording()
    editor.save_undo_state()
    MapManager.load_preset(physics, name)
    camera.x, camera.y = 0.0, 0.0
    editor.selected_entity = None
    mark_cache_dirty()

def save_map():
    MapManager.save_map(physics, os.path.join(MAPS_DIR, "map.json"))
    print("Map saved to maps/map.json")

def load_map():
    global is_recording
    if is_recording:
        stop_realtime_recording()
    editor.save_undo_state()
    if MapManager.load_map(physics, os.path.join(MAPS_DIR, "map.json")):
        camera.x, camera.y = 0.0, 0.0
        editor.selected_entity = None
        mark_cache_dirty()
        print("Map loaded from maps/map.json")

def render_physics_scene(target_surface, target_glow_surf, render_cam, draw_hud_overlay=False):
    # A. Draw base background
    target_surface.fill(UITheme.BG_DARK_SOLID)
    
    # B. Draw Pymunk Physics Entities
    # Draw portals
    for portal in physics.portals:
        draw_neon_circle(target_surface, portal['pos_a'], portal['radius'], portal['color'], width=2, camera=render_cam, glow_surf=target_glow_surf)
        draw_neon_circle(target_surface, portal['pos_b'], portal['radius'], portal['color'], width=2, camera=render_cam, glow_surf=target_glow_surf)
        
    # Draw finish lines
    for finish in physics.finish_lines:
        draw_neon_line(target_surface, finish['p1'], finish['p2'], finish['color'], 4, render_cam, glow_surf=target_glow_surf)
        
    # Draw boosters
    for booster in physics.boosters:
        draw_neon_line(target_surface, booster['p1'], booster['p2'], booster['color'], 5, render_cam, glow_surf=target_glow_surf)
        cx = (booster['p1'][0] + booster['p2'][0]) / 2.0
        cy = (booster['p1'][1] + booster['p2'][1]) / 2.0
        dx = booster['direction'][0] * 0.4
        dy = booster['direction'][1] * 0.4
        draw_neon_line(target_surface, (cx, cy), (cx + dx, cy + dy), booster['color'], 2, render_cam, glow_surf=target_glow_surf)
        
    # Draw walls
    for wall in physics.walls:
        draw_neon_line(target_surface, wall.a, wall.b, wall.color, 3, render_cam, glow_surf=target_glow_surf)
        
    # Draw boxes
    for box in physics.boxes:
        verts = box.get_vertices()
        world_verts = [box.body.local_to_world(v) for v in verts]
        scr_verts = [render_cam.world_to_screen(wv) for wv in world_verts]
        pygame.draw.polygon(target_surface, (*box.color, 120), scr_verts)
        for i in range(len(world_verts)):
            p1 = world_verts[i]
            p2 = world_verts[(i + 1) % len(world_verts)]
            draw_neon_line(target_surface, p1, p2, box.color, 2, render_cam, glow_surf=target_glow_surf)
            
    # Draw conveyors
    for conv in physics.conveyors:
        draw_neon_line(target_surface, conv['p1'], conv['p2'], conv['color'], 5, render_cam, glow_surf=target_glow_surf)
        p1_scr = render_cam.world_to_screen(conv['p1'])
        p2_scr = render_cam.world_to_screen(conv['p2'])
        dx = p2_scr[0] - p1_scr[0]
        dy = p2_scr[1] - p1_scr[1]
        length = math.hypot(dx, dy)
        if length > 0:
            ux = dx / length
            uy = dy / length
            
            # Sync conveyor dots visual movement speed with physical conveyor speed
            step_size_world = 0.5  # spacing of conveyor dots in world units
            offset_world = (simulation.sim_time * conv['speed']) % step_size_world
            offset = offset_world * render_cam.zoom
            step_size_scr = max(4.0, step_size_world * render_cam.zoom)
            
            d = offset
            while d < length:
                px = p1_scr[0] + ux * d
                py = p1_scr[1] + uy * d
                pygame.draw.circle(target_surface, (255, 255, 255), (int(px), int(py)), 3)
                d += step_size_scr
                
    # Draw escalators
    for esc in physics.escalators:
        p1_scr = render_cam.world_to_screen(esc['p1'])
        p2_scr = render_cam.world_to_screen(esc['p2'])
        
        # Mute the base guide line during simulation so it doesn't distract from the steps
        if simulation.running:
            pygame.draw.line(target_surface, (50, 60, 75), p1_scr, p2_scr, 1)
        else:
            draw_neon_line(target_surface, esc['p1'], esc['p2'], esc['color'], 5, render_cam, glow_surf=target_glow_surf)
            
        steps = esc.get('steps', [])
        for body, tread, riser in steps:
            # Get world coordinates of tread endpoints (which are physically clipped in Pymunk)
            ta_w = body.local_to_world(tread.a)
            tb_w = body.local_to_world(tread.b)
            
            if math.hypot(ta_w.x - tb_w.x, ta_w.y - tb_w.y) > 0.02:
                ta = render_cam.world_to_screen(ta_w)
                tb = render_cam.world_to_screen(tb_w)
                pygame.draw.line(target_surface, (255, 255, 255), ta, tb, 2)
            
            # Get world coordinates of riser endpoints (which are physically clipped in Pymunk)
            ra_w = body.local_to_world(riser.a)
            rb_w = body.local_to_world(riser.b)
            
            if math.hypot(ra_w.x - rb_w.x, ra_w.y - rb_w.y) > 0.02:
                ra = render_cam.world_to_screen(ra_w)
                rb = render_cam.world_to_screen(rb_w)
                pygame.draw.line(target_surface, (255, 255, 255), ra, rb, 2)

    # Draw elevators
    for elev in physics.elevators:
        body = elev['body']
        w_half = elev['width'] / 2.0
        h_half = elev['height'] / 2.0
        local_verts = [(-w_half, -h_half), (w_half, -h_half), (w_half, h_half), (-w_half, h_half)]
        world_verts = [body.local_to_world(v) for v in local_verts]
        scr_verts = [render_cam.world_to_screen(wv) for wv in world_verts]
        pygame.draw.polygon(target_surface, (*elev['color'], 80), scr_verts)
        for i in range(len(world_verts)):
            p1 = world_verts[i]
            p2 = world_verts[(i + 1) % len(world_verts)]
            draw_neon_line(target_surface, p1, p2, elev['color'], 3, render_cam, glow_surf=target_glow_surf)
        p_ctr = render_cam.world_to_screen(body.position)
        w_scr = int(elev['width'] * render_cam.zoom)
        pygame.draw.line(target_surface, (255, 255, 255), (p_ctr[0] - w_scr//2, p_ctr[1]), (p_ctr[0] + w_scr//2, p_ctr[1]), 1)

    # Draw seesaws
    for ss in physics.seesaws:
        body = ss['body']
        w_half = ss['length'] / 2.0
        h_half = ss['thickness'] / 2.0
        local_verts = [(-w_half, -h_half), (w_half, -h_half), (w_half, h_half), (-w_half, h_half)]
        world_verts = [body.local_to_world(v) for v in local_verts]
        scr_verts = [render_cam.world_to_screen(wv) for wv in world_verts]
        pygame.draw.polygon(target_surface, (*ss['color'], 100), scr_verts)
        for i in range(len(world_verts)):
            p1 = world_verts[i]
            p2 = world_verts[(i + 1) % len(world_verts)]
            draw_neon_line(target_surface, p1, p2, ss['color'], 3, render_cam, glow_surf=target_glow_surf)
        scr_pivot = render_cam.world_to_screen(ss['pos'])
        pygame.draw.circle(target_surface, (255, 255, 255), scr_pivot, 4)

    # Draw spinners
    for sp in physics.spinners:
        body = sp['body']
        for shape in sp['shapes']:
            verts = shape.get_vertices()
            world_verts = [body.local_to_world(v) for v in verts]
            scr_verts = [render_cam.world_to_screen(wv) for wv in world_verts]
            pygame.draw.polygon(target_surface, (*sp['color'], 100), scr_verts)
            for i in range(len(world_verts)):
                p1 = world_verts[i]
                p2 = world_verts[(i + 1) % len(world_verts)]
                draw_neon_line(target_surface, p1, p2, sp['color'], 2, render_cam, glow_surf=target_glow_surf)
        scr_pivot = render_cam.world_to_screen(sp['pos'])
        pygame.draw.circle(target_surface, (255, 255, 255), scr_pivot, 5)

    # Draw Spawners
    for spawner in physics.spawners:
        draw_neon_circle(target_surface, spawner['pos'], 0.7, spawner['color'], width=1, camera=render_cam, glow_surf=target_glow_surf)
        scr_center = render_cam.world_to_screen(spawner['pos'])
        pygame.draw.circle(target_surface, spawner['color'], scr_center, 6)

    # Draw trails
    for marble in physics.marbles:
        if len(marble.trail) < 2:
            continue
        color = marble.color
        for i in range(len(marble.trail) - 1):
            p1 = marble.trail[i]
            p2 = marble.trail[i+1]
            alpha = int(180 * (i / len(marble.trail)))
            if alpha <= 0:
                continue
            p1_scr = render_cam.world_to_screen(p1)
            p2_scr = render_cam.world_to_screen(p2)
            thickness = max(1, int(marble.radius * render_cam.zoom * (i / len(marble.trail))))
            pygame.draw.line(target_glow_surf, (*color, alpha), p1_scr, p2_scr, thickness)

    # Blit glows
    target_surface.blit(target_glow_surf, (0, 0))

    # Draw active rolling marbles
    for marble in physics.marbles:
        center = render_cam.world_to_screen(marble.body.position)
        rad = int(marble.radius * render_cam.zoom)
        if rad > 0:
            pygame.draw.circle(target_surface, marble.color, center, rad)
            pygame.draw.circle(target_surface, (255, 255, 255), center, rad, width=1)
            angle = marble.body.angle
            rx = marble.radius * math.cos(angle)
            ry = marble.radius * math.sin(angle)
            edge_pos = (marble.body.position.x + rx, marble.body.position.y + ry)
            edge_scr = render_cam.world_to_screen(edge_pos)
            pygame.draw.line(target_surface, (0, 0, 0), center, edge_scr, 2)

    # Standings HUD
    if draw_hud_overlay and simulation.running:
        scaled_font = pygame.font.SysFont(UITheme.FONT_NAME, int(15 * (target_surface.get_width() / width)))
        simulation.draw_hud(target_surface, scaled_font)

def merge_audio_video(temp_video, temp_audio, final_video):
    """Muxes the recorded video + audio into the final MP4 (synchronous)."""
    print("Merging audio and video...")
    cmd = [
        'ffmpeg', '-y',
        '-i', temp_video,
        '-i', temp_audio,
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        final_video
    ]
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(cmd, startupinfo=startupinfo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print(f"Merge successful! Video saved to {final_video}")
            # Clean up temporary files safely
            for tmp in (temp_video, temp_audio):
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except Exception as e:
                        print(f"Error removing temp file {tmp}: {e}")
            return True
        else:
            print(f"FFmpeg merge failed with return code {result.returncode}")
            print(f"FFmpeg stderr: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error during audio/video merge: {e}")
        return False

def merge_audio_video_async(temp_video, temp_audio, final_video):
    thread = threading.Thread(target=merge_audio_video, args=(temp_video, temp_audio, final_video))
    thread.daemon = True
    thread.start()

def toggle_recording():
    global is_recording
    if is_recording:
        stop_realtime_recording()
    else:
        start_realtime_recording()

def start_realtime_recording():
    global is_recording, recording_frame_count
    
    # 1. Reset/Start simulation
    if not simulation.running:
        toggle_play_state()
    else:
        simulation.start()
        
    # 2. Start sound manager recording
    SoundManager.get_instance().start_recording()
    
    # 3. Start video exporter
    temp_video_path = os.path.join(EXPORTS_DIR, "temp_video.mp4")
    # Ensure export folder exists
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    
    success = video_exporter.start_recording(temp_video_path, width, height, fps=60)
    if success:
        is_recording = True
        recording_frame_count = 0
        print("Real-time recording started.")
    else:
        print("Failed to start real-time video recording.")
        
    build_ui()

def stop_realtime_recording():
    global is_recording, recording_frame_count, last_take_seed
    if not is_recording:
        return

    is_recording = False

    # 1. Stop video exporter
    video_exporter.stop_recording()

    # 2. Stop sound manager recording
    temp_video_path = os.path.join(EXPORTS_DIR, "temp_video.mp4")
    temp_audio_path = os.path.join(EXPORTS_DIR, "temp_audio.wav")
    final_video_path = os.path.join(EXPORTS_DIR, f"marble_race_{_timestamp()}.mp4")

    duration_sec = recording_frame_count / 60.0
    SoundManager.get_instance().stop_recording(temp_audio_path, duration_sec)

    # 3. Stop simulation and remember this run's seed so RENDER HQ can reproduce it
    last_take_seed = simulation.seed
    simulation.stop()

    # 4. Merge audio and video asynchronously
    merge_audio_video_async(temp_video_path, temp_audio_path, final_video_path)

    build_ui()

def _render_stop_button_rect():
    """Rect of the STOP & SAVE button shown during offline rendering."""
    bw, bh = 220, 48
    return pygame.Rect((width - bw) // 2, int(height * 0.78), bw, bh)

def _draw_render_overlay(frame, frame_idx, sim_time, stop_rect, out_w, out_h):
    """Draws the live preview + STOP button while offline rendering is in progress."""
    screen.fill(UITheme.BG_DARK_SOLID)

    # Title
    title = pygame.font.SysFont(UITheme.FONT_NAME, 24, bold=True)
    title_surf = title.render("RENDERING HQ", True, UITheme.ACCENT_CYAN)
    screen.blit(title_surf, title_surf.get_rect(center=(width // 2, int(height * 0.12))))

    # Small live preview, scaled to fit a box while preserving the output aspect ratio
    box_w, box_h = int(width * 0.45), int(height * 0.5)
    scale = min(box_w / out_w, box_h / out_h)
    pv_w, pv_h = max(1, int(out_w * scale)), max(1, int(out_h * scale))
    pv_x = (width - pv_w) // 2
    pv_y = int(height * 0.18)
    preview = pygame.transform.smoothscale(frame, (pv_w, pv_h))
    screen.blit(preview, (pv_x, pv_y))
    pygame.draw.rect(screen, UITheme.BORDER, (pv_x, pv_y, pv_w, pv_h), width=1)

    # Info line (frame count + sim time + quality)
    info = pygame.font.SysFont(UITheme.FONT_NAME, 16)
    line = f"frame {frame_idx}   |   {sim_time:.2f}s   |   {out_w}x{out_h}  2x SS   |   frame-locked 60fps"
    info_surf = info.render(line, True, UITheme.TEXT_MUTED)
    screen.blit(info_surf, info_surf.get_rect(center=(width // 2, pv_y + pv_h + 28)))

    # STOP button (hover highlight)
    hovered = stop_rect.collidepoint(pygame.mouse.get_pos())
    btn_color = (255, 90, 90) if hovered else (210, 60, 60)
    pygame.draw.rect(screen, btn_color, stop_rect, border_radius=8)
    pygame.draw.rect(screen, (255, 160, 160), stop_rect, width=1, border_radius=8)
    btn_font = pygame.font.SysFont(UITheme.FONT_NAME, 18, bold=True)
    btn_surf = btn_font.render("STOP & SAVE", True, (255, 255, 255))
    screen.blit(btn_surf, btn_surf.get_rect(center=stop_rect.center))

    hint = pygame.font.SysFont(UITheme.FONT_NAME, 13)
    hint_surf = hint.render("Click STOP (or press ESC) to finish and save the video", True, UITheme.TEXT_MUTED)
    screen.blit(hint_surf, hint_surf.get_rect(center=(width // 2, stop_rect.bottom + 24)))
    pygame.display.flip()

def _draw_saving_overlay(tick, status_text):
    """Animated spinner shown while the render is being encoded/saved."""
    screen.fill(UITheme.BG_DARK_SOLID)
    cx, cy = width // 2, height // 2

    title = pygame.font.SysFont(UITheme.FONT_NAME, 24, bold=True)
    ts = title.render("SAVING RENDER", True, UITheme.ACCENT_CYAN)
    screen.blit(ts, ts.get_rect(center=(cx, cy - 80)))

    # Spinner: dots around a circle with a fading comet trail
    n = 12
    radius = 28
    lead = (tick // 2) % n
    for i in range(n):
        ang = 2.0 * math.pi * i / n - math.pi / 2.0
        phase = (lead - i) % n
        b = 1.0 - phase / n
        col = (int(40 + 215 * b), int(60 + 195 * b), int(80 + 175 * b))
        px = int(cx + radius * math.cos(ang))
        py = int(cy + radius * math.sin(ang))
        pygame.draw.circle(screen, col, (px, py), 4)

    st = pygame.font.SysFont(UITheme.FONT_NAME, 16)
    ss = st.render(status_text, True, UITheme.TEXT_LIGHT)
    screen.blit(ss, ss.get_rect(center=(cx, cy + 72)))
    hint = pygame.font.SysFont(UITheme.FONT_NAME, 13)
    hs = hint.render("Please wait — encoding in progress", True, UITheme.TEXT_MUTED)
    screen.blit(hs, hs.get_rect(center=(cx, cy + 100)))
    pygame.display.flip()

def render_hq_take():
    """Renders the race offline at high quality with a manual stop.

    Each frame advances the simulation by a fixed dt (1/60s) decoupled from the
    wall clock, so however long a frame takes to render the animation stays
    perfectly smooth (frame-locked). If a live take was just played its seed is
    reused so the same race is reproduced; otherwise a fresh deterministic race
    is generated. The render length is controlled manually via the STOP button."""
    global is_recording
    # Make sure we are not mid-playback/recording first
    if is_recording:
        stop_realtime_recording()
    if simulation.running:
        toggle_play_state()

    seed = last_take_seed if last_take_seed else None
    editor.save_undo_state()
    run_offline_render(seed)

def run_offline_render(seed):
    SS = 2  # supersample factor (render at 2x then downscale for anti-aliasing)
    SAFETY_CAP = 60 * 60 * 5  # hard limit: 5 minutes of footage

    rf = editor.render_frame
    use_frame = rf is not None

    if use_frame:
        OUT_W, OUT_H = RENDER_FORMATS[rf["format"]]
    else:
        OUT_W, OUT_H = 1920, 1080
    HI_W, HI_H = OUT_W * SS, OUT_H * SS

    hud_font = pygame.font.SysFont(UITheme.FONT_NAME, 16)

    cam_backup = simulation.camera
    speed_backup = simulation.speed_multiplier
    mode_backup = simulation.camera_mode
    simulation.speed_multiplier = 1.0

    rotated = use_frame and abs(rf["angle"]) > 1e-4
    if use_frame:
        # Static shot framed on the render region. When rotated we render into a square
        # large enough to contain the frame, then rotate-and-crop to the output rect.
        fw, fh = render_frame_size(rf)
        zoom_hi = HI_H / float(rf["height"])
        if rotated:
            cam_dim = int(math.ceil(math.hypot(HI_W, HI_H)))
        else:
            cam_dim = max(HI_W, HI_H)
        render_cam = Camera(HI_W if not rotated else cam_dim, HI_H if not rotated else cam_dim)
        render_cam.x, render_cam.y = rf["pos"]
        render_cam.zoom = zoom_hi
        render_cam.min_zoom, render_cam.max_zoom = 1e-3, 1e9
        surf_w, surf_h = render_cam.screen_width, render_cam.screen_height
        # The render camera is fixed on the frame; keep follow-mode from moving the live cam
        simulation.camera = Camera(10, 10)
        simulation.camera_mode = "free"
    else:
        render_cam = Camera(HI_W, HI_H)
        render_cam.x, render_cam.y = camera.x, camera.y
        render_cam.zoom = camera.zoom * (HI_H / float(height))
        render_cam.min_zoom, render_cam.max_zoom = 1e-3, 1e9
        surf_w, surf_h = HI_W, HI_H
        simulation.camera = render_cam

    hi_surf = pygame.Surface((surf_w, surf_h))
    hi_glow = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)

    simulation.start(seed=seed)

    sm = SoundManager.get_instance()
    sm.start_recording()
    sm.offline = True

    os.makedirs(EXPORTS_DIR, exist_ok=True)
    temp_video = os.path.join(EXPORTS_DIR, "hq_temp_video.mp4")
    temp_audio = os.path.join(EXPORTS_DIR, "hq_temp_audio.wav")
    final_video = os.path.join(EXPORTS_DIR, f"marble_race_hq_{_timestamp()}.mp4")

    if not video_exporter.start_recording(temp_video, OUT_W, OUT_H, fps=60):
        print("RENDER HQ: failed to open the video writer.")
        sm.offline = False
        sm.recording = False
        simulation.stop()
        simulation.camera = cam_backup
        simulation.speed_multiplier = speed_backup
        simulation.camera_mode = mode_backup
        return

    label = (rf["format"] if use_frame else "live cam")
    print(f"RENDER HQ: rendering {OUT_W}x{OUT_H} [{label}] ({SS}x SS) until stopped...")
    stop_rect = _render_stop_button_rect()
    rendered = 0
    stop = False
    while not stop and rendered < SAFETY_CAP:
        # Handle stop interactions while keeping the window responsive
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                stop = True
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                stop = True
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and stop_rect.collidepoint(ev.pos):
                stop = True
        if stop:
            break

        # Advance exactly one frame of simulation time (frame-locked, not wall-clock)
        if use_frame:
            sm.camera_pos = rf["pos"]
            sm.view_half_width = fw / 2.0
        else:
            sm.camera_pos = (render_cam.x, render_cam.y)
            sm.view_half_width = (HI_W / 2.0) / render_cam.zoom
        simulation.update()

        # Render the world supersampled (no HUD)
        hi_glow.fill((0, 0, 0, 0))
        render_physics_scene(hi_surf, hi_glow, render_cam, draw_hud_overlay=False)

        if rotated:
            # Rotate the rendered square so the frame becomes upright, then crop center
            rot = pygame.transform.rotate(hi_surf, -math.degrees(rf["angle"]))
            crop = pygame.Rect(0, 0, HI_W, HI_H)
            crop.center = rot.get_rect().center
            cropped = pygame.Surface((HI_W, HI_H))
            cropped.blit(rot, (0, 0), crop)
            frame = pygame.transform.smoothscale(cropped, (OUT_W, OUT_H))
        else:
            frame = pygame.transform.smoothscale(hi_surf, (OUT_W, OUT_H))

        simulation.draw_hud(frame, hud_font)
        video_exporter.write_frame(frame)
        rendered += 1

        # Update the small preview a few times per second (cheap, offline)
        if rendered % 3 == 0:
            _draw_render_overlay(frame, rendered, simulation.sim_time, stop_rect, OUT_W, OUT_H)

    # Finalize. The audio mixdown + FFmpeg encode are heavy and synchronous, so run
    # them on a worker thread and animate a spinner on the main thread instead of
    # letting the window freeze.
    capped = " (safety cap reached)" if rendered >= SAFETY_CAP else ""
    if rendered > 0:
        status = {'text': 'Finalizing video frames...', 'done': False}

        def finalize():
            video_exporter.stop_recording()
            status['text'] = 'Mixing spatial audio...'
            sm.stop_recording(temp_audio, rendered / 60.0)
            status['text'] = 'Encoding final MP4 (FFmpeg)...'
            merge_audio_video(temp_video, temp_audio, final_video)
            status['done'] = True

        worker = threading.Thread(target=finalize, daemon=True)
        worker.start()

        spin_clock = pygame.time.Clock()
        tick = 0
        while not status['done']:
            pygame.event.pump()  # keep the window responsive (ignore input while saving)
            _draw_saving_overlay(tick, status['text'])
            tick += 1
            spin_clock.tick(30)

        print(f"RENDER HQ: {rendered} frames done{capped}; saved -> {final_video}")
    else:
        video_exporter.stop_recording()
        sm.stop_recording(temp_audio, 0.0)
        print("RENDER HQ: stopped before any frame was rendered.")

    sm.offline = False
    simulation.stop()
    simulation.camera = cam_backup
    simulation.speed_multiplier = speed_backup
    simulation.camera_mode = mode_backup
    build_ui()

def bake_to(target_frames):
    """Simulate forward and fill the cache up to ``target_frames`` frames.

    Events are logged silently into the cache (no live audio) so the baked race
    can later be exported with sound. ESC stops early, leaving a partial cache.
    Deterministic: if the cache is empty it (re)seeds from cache.seed first."""
    global cache, playhead, playing, cache_dirty
    if cache is None or cache_dirty:
        enter_camera_mode()
    target = max(1, int(target_frames))
    if cache.n_cached >= target:
        return

    sm = SoundManager.get_instance()
    prev_offline, prev_recording = sm.offline, sm.recording

    # If we haven't stepped past the initial snapshot, reseed so the bake is the
    # deterministic race for cache.seed.
    if cache.n_cached <= 1:
        simulation.start(seed=cache.seed)
        cache.frames.clear()
        cache.append(capture_snapshot(physics), physics)

    sm.offline = True
    sm.start_recording()

    aborted = False
    while cache.n_cached < target:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                aborted = True
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                aborted = True
        if aborted:
            break

        simulation.step_one_frame()
        cache.append(capture_snapshot(physics), physics)

        done = cache.n_cached
        if done % 5 == 0 or done >= target:
            _draw_saving_overlay(done, f"Baking {done}/{target}")
            pygame.event.pump()

    # Capture the logged audio into the cache for later export, then restore.
    cache.audio_events = list(sm.recorded_events)
    cache.rolling_env = list(sm.rolling_envelope)
    sm.recording = prev_recording
    sm.offline = prev_offline

    playhead = min(playhead, cache.n_cached - 1)
    playing = False

def toggle_grid_snap():
    editor.grid_snap = not editor.grid_snap
    build_ui()

def toggle_camera_mode():
    if simulation.camera_mode == "free":
        simulation.camera_mode = "leader"
    else:
        simulation.camera_mode = "free"
    build_ui()

# Build initial buttons list
build_ui()

# Toolbar buttons for drawing tools (placed vertically on the left side of screen)
left_tools = [
    {"name": "select", "label": "SELECTOR", "tooltip": "Select and edit properties"},
    {"name": "wall", "label": "WALL", "tooltip": "Draw static line walls"},
    {"name": "box", "label": "BOX", "tooltip": "Draw static obstacle box"},
    {"name": "booster", "label": "BOOSTER", "tooltip": "Draw accelerator pads"},
    {"name": "conveyor", "label": "CONVEYOR", "tooltip": "Draw conveyor belt"},
    {"name": "escalator", "label": "ESCALATOR", "tooltip": "Draw escalator steps"},
    {"name": "elevator", "label": "ELEVATOR", "tooltip": "Place vertical lifting platform"},
    {"name": "seesaw", "label": "SEESAW", "tooltip": "Place pivot seesaw bar"},
    {"name": "spinner", "label": "SPINNER", "tooltip": "Place rotating spinner"},
    {"name": "portal", "label": "PORTAL", "tooltip": "Create teleporter nodes (A to B)"},
    {"name": "spawner", "label": "SPAWNER", "tooltip": "Place marble generators"},
    {"name": "finish", "label": "FINISH LINE", "tooltip": "Draw race finish line"},
    {"name": "renderframe", "label": "RENDER CAM", "tooltip": "Drag to place the render region; move/rotate/scale it like any object. RENDER HQ exports what's inside."},
    {"name": "eraser", "label": "ERASER", "tooltip": "Delete objects under cursor"}
]
tool_buttons = []
def build_tool_buttons():
    tool_buttons.clear()
    y_start = 80
    for t in left_tools:
        btn = Button(15, y_start, 130, 32, t["label"], tooltip=t["tooltip"])
        btn.selected = (editor.active_tool == t["name"])
        tool_buttons.append((t["name"], btn))
        y_start += 40

build_tool_buttons()

# Inspector sidebar dimensions
sidebar_rect = pygame.Rect(width - SIDEBAR_WIDTH, TOOLBAR_HEIGHT, SIDEBAR_WIDTH, height - TOOLBAR_HEIGHT)

# Glow surface for optimized neon drawing (prevents memory allocation lag)
glow_surf = pygame.Surface((width, height), pygame.SRCALPHA)

# Bottom timeline bar (CAMERA mode)
timeline = TimelineBar(width, height)
timeline.layout(seq_len)

# Main clock
clock = pygame.time.Clock()

# Main Game Loop
while True:
    # 1. Event Handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            if video_exporter.recording:
                video_exporter.stop_recording()
            pygame.quit()
            sys.exit(0)
            
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if video_exporter.recording:
                    video_exporter.stop_recording()
                pygame.quit()
                sys.exit(0)
            elif event.key == pygame.K_SPACE:
                if mode == "camera":
                    playing = not playing
                else:
                    toggle_play_state()
            elif event.key == pygame.K_g:
                toggle_grid_snap()
            elif event.key == pygame.K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                editor.undo()
            elif event.key == pygame.K_y and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                editor.redo()
                
        elif event.type == pygame.MOUSEBUTTONDOWN:
            m_pos = event.pos
            # A. Check if toolbar clicked
            in_toolbar = m_pos[1] < TOOLBAR_HEIGHT

            # B. Check if sidebar inspector clicked
            in_sidebar = m_pos[0] >= (width - SIDEBAR_WIDTH)

            # C. Check if left tools menu clicked
            in_tools_menu = m_pos[0] < 160 and m_pos[1] >= TOOLBAR_HEIGHT and m_pos[1] < (80 + len(left_tools) * 40)

            # CAMERA mode: toolbar still works; timeline bar handles the rest.
            if mode == "camera":
                if in_toolbar:
                    for btn in buttons:
                        btn.check_click(m_pos)
                elif event.button == 1:
                    action = timeline.hit(m_pos)
                    if action == "play":
                        playing = True
                    elif action == "pause":
                        playing = False
                    elif action == "reset":
                        playhead = 0
                        playing = False
                    elif action == "bake":
                        bake_to(seq_len)
                        build_ui()
                    elif action in ("len_150", "len_250", "len_500", "len_1000"):
                        seq_len = int(action.split("_")[1])
                        cache_dirty = True
                        playing = False
                        timeline.layout(seq_len)
                    elif action == "len_minus":
                        seq_len = max(30, seq_len - 30)
                        cache_dirty = True
                        playing = False
                        timeline.layout(seq_len)
                    elif action == "len_plus":
                        seq_len = max(30, seq_len + 30)
                        cache_dirty = True
                        playing = False
                        timeline.layout(seq_len)
                    elif action and action.startswith("scrub:"):
                        f = int(action.split(":")[1])
                        if cache is not None and f < cache.n_cached:
                            playhead = f
                            playing = False
                elif event.button in (2, 3):
                    panning = True
                    pan_start_pos = m_pos
                continue

            if in_toolbar:
                for btn in buttons:
                    btn.check_click(m_pos)
            elif in_sidebar:
                # Check delete button click (it is drawn inside inspector, let's check its coordinate here)
                del_rect = pygame.Rect(width - SIDEBAR_WIDTH + 20, height - 60, SIDEBAR_WIDTH - 40, 36)
                if event.button == 1 and del_rect.collidepoint(m_pos):
                    if editor.selected_entity:
                        editor.save_undo_state()
                        editor.delete_entity(editor.selected_entity)
                        editor.selected_entity = None
                        mark_cache_dirty()
                else:
                    editor.handle_inspector_click(m_pos)
                    mark_cache_dirty()
            elif in_tools_menu:
                for t_name, btn in tool_buttons:
                    if btn.check_click(m_pos):
                        editor.active_tool = t_name
                        build_tool_buttons()
            else:
                # Click in sandbox
                if event.button == 1: # Left Click
                    editor.handle_mouse_down(m_pos, 1)
                elif event.button in [2, 3]: # Middle or Right click to pan
                    panning = True
                    pan_start_pos = m_pos
                    
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                # Release left click (stop drawing)
                editor.handle_mouse_up(event.pos, 1)
                if mode == "edit":
                    mark_cache_dirty()
                # Release slider drags on sidebar
                for name, slider in editor.sliders.items():
                    slider.handle_event(event)
            elif event.button in [2, 3]:
                panning = False
                
        elif event.type == pygame.MOUSEMOTION:
            if panning:
                # Drag camera
                dx = event.pos[0] - pan_start_pos[0]
                dy = event.pos[1] - pan_start_pos[1]
                camera.pan(dx, dy)
                pan_start_pos = event.pos
            else:
                # Forward sandbox motion to editor for object dragging
                if event.pos[0] < (width - SIDEBAR_WIDTH) and event.pos[1] >= TOOLBAR_HEIGHT:
                    editor.handle_mouse_move(event.pos)
                    
                # Forward motion events to sliders on sidebar
                if event.pos[0] >= (width - SIDEBAR_WIDTH):
                    for name, slider in editor.sliders.items():
                        slider.handle_event(event)
                        
        elif event.type == pygame.MOUSEWHEEL:
            # Zoom centered under cursor
            zoom_factor = 1.1 if event.y > 0 else 0.9
            camera.zoom_at(pygame.mouse.get_pos(), zoom_factor)

    # 2. Physics & State Updating
    sound_mgr = SoundManager.get_instance()
    sound_mgr.camera_pos = (camera.x, camera.y)
    # Keep the audio listener's spatial scale in sync with the camera zoom so panning
    # and distance falloff always match what is currently visible on screen.
    sound_mgr.view_half_width = (width / 2.0) / camera.zoom

    if mode == "camera":
        # Timeline-driven advance when playing.
        if playing and cache is not None:
            if playhead < cache.n_cached - 1:
                # Silent cache playback — just advance the playhead.
                playhead += 1
            elif cache.n_cached < seq_len:
                # Live frontier: step the sim, append, play live sound.
                sound_mgr.offline = False
                sound_mgr.recording = False
                simulation.step_one_frame()
                cache.append(capture_snapshot(physics), physics)
                playhead = cache.n_cached - 1
            else:
                # At the end with a full cache.
                playing = False

        # 3. Rendering (CAMERA): draw the cached frame, render guide, then timeline.
        glow_surf.fill((0, 0, 0, 0))
        snap = cache.get(playhead) if cache is not None else None
        if snap is not None:
            draw_snapshot(screen, glow_surf, camera, physics, snap, cache.marble_table, playhead / 60.0)
        else:
            screen.fill(UITheme.BG_DARK_SOLID)
        editor.draw_render_frame(screen)

        # Toolbar (kept visible so EDIT/CAMERA toggle and map buttons stay reachable).
        toolbar_rect = pygame.Rect(0, 0, width, TOOLBAR_HEIGHT)
        pygame.draw.rect(screen, UITheme.BG_DARK, toolbar_rect, border_radius=0)
        pygame.draw.rect(screen, UITheme.BORDER, toolbar_rect, width=1)
        title_font = pygame.font.SysFont(UITheme.FONT_NAME, 18, bold=True)
        title_surf = title_font.render("MARBLE PHYSICS LAB", True, UITheme.ACCENT_CYAN)
        screen.blit(title_surf, title_surf.get_rect(midleft=(15, TOOLBAR_HEIGHT / 2.0)))
        cam_tooltip = None
        for btn in buttons:
            tt = btn.draw(screen, font_medium)
            if tt:
                cam_tooltip = tt

        timeline.layout(seq_len)
        timeline.draw(screen, font_medium, playhead, seq_len, cache.n_cached if cache else 0, playing)
        if cam_tooltip:
            Tooltip.draw(screen, cam_tooltip, pygame.mouse.get_pos(), font_medium)
        pygame.display.flip()
        clock.tick(60)
        continue

    simulation.update()

    # 3. Rendering
    # A. Render base physics scene (fills background, draws neon bodies, trails, marbles, HUD standings)
    glow_surf.fill((0, 0, 0, 0))
    render_physics_scene(screen, glow_surf, camera, draw_hud_overlay=simulation.running)

    # Capture clean frame for recording if recording is active
    if is_recording:
        video_exporter.write_frame(screen)
        recording_frame_count += 1
        if recording_frame_count >= 3600:  # 60 seconds safety limit
            stop_realtime_recording()

    # B. Draw editor overlays on top of the physics scene (only in edit mode)
    if not simulation.running:
        editor.draw_grid(screen)
        editor.draw_previews(screen)
        editor.draw_render_frame(screen)

        # Draw selection bounds around selected entity
        if editor.selected_entity:
            type_str, obj = editor.selected_entity
            if type_str == "wall" or type_str == "finish":
                p1 = obj.a if type_str == "wall" else obj['p1']
                p2 = obj.b if type_str == "wall" else obj['p2']
                draw_neon_line(screen, p1, p2, UITheme.ACCENT_CYAN, 5, camera, glow_surf=glow_surf)
            elif type_str == "booster":
                draw_neon_line(screen, obj['p1'], obj['p2'], UITheme.ACCENT_CYAN, 7, camera, glow_surf=glow_surf)
            elif type_str in ["conveyor", "escalator"]:
                draw_neon_line(screen, obj['p1'], obj['p2'], UITheme.ACCENT_CYAN, 7, camera, glow_surf=glow_surf)
            elif type_str == "spawner":
                draw_neon_circle(screen, obj['pos'], 0.8, UITheme.ACCENT_CYAN, width=1, camera=camera, glow_surf=glow_surf)
            elif type_str == "portal_a":
                draw_neon_circle(screen, obj['pos_a'], obj['radius'] + 0.1, UITheme.ACCENT_CYAN, width=1, camera=camera, glow_surf=glow_surf)
            elif type_str == "portal_b":
                draw_neon_circle(screen, obj['pos_b'], obj['radius'] + 0.1, UITheme.ACCENT_CYAN, width=1, camera=camera, glow_surf=glow_surf)
            elif type_str == "box":
                verts = obj.get_vertices()
                world_verts = [obj.body.local_to_world(v) for v in verts]
                for i in range(len(world_verts)):
                    p1 = world_verts[i]
                    p2 = world_verts[(i + 1) % len(world_verts)]
                    draw_neon_line(screen, p1, p2, UITheme.ACCENT_CYAN, 3, camera, glow_surf=glow_surf)
            elif type_str == "elevator":
                body = obj['body']
                w_half = obj['width'] / 2.0
                h_half = obj['height'] / 2.0
                local_verts = [(-w_half, -h_half), (w_half, -h_half), (w_half, h_half), (-w_half, h_half)]
                world_verts = [body.local_to_world(v) for v in local_verts]
                for i in range(len(world_verts)):
                    p1 = world_verts[i]
                    p2 = world_verts[(i + 1) % len(world_verts)]
                    draw_neon_line(screen, p1, p2, UITheme.ACCENT_CYAN, 3, camera, glow_surf=glow_surf)
            elif type_str == "seesaw":
                body = obj['body']
                w_half = obj['length'] / 2.0
                h_half = obj['thickness'] / 2.0
                local_verts = [(-w_half, -h_half), (w_half, -h_half), (w_half, h_half), (-w_half, h_half)]
                world_verts = [body.local_to_world(v) for v in local_verts]
                for i in range(len(world_verts)):
                    p1 = world_verts[i]
                    p2 = world_verts[(i + 1) % len(world_verts)]
                    draw_neon_line(screen, p1, p2, UITheme.ACCENT_CYAN, 3, camera, glow_surf=glow_surf)
            elif type_str == "spinner":
                body = obj['body']
                for shape in obj['shapes']:
                    verts = shape.get_vertices()
                    world_verts = [body.local_to_world(v) for v in verts]
                    for i in range(len(world_verts)):
                        p1 = world_verts[i]
                        p2 = world_verts[(i + 1) % len(world_verts)]
                        draw_neon_line(screen, p1, p2, UITheme.ACCENT_CYAN, 3, camera, glow_surf=glow_surf)
                        
            # Apply glow additions
            screen.blit(glow_surf, (0, 0))
            
        # Draw handles
        editor.draw_handles(screen)
        
    # E. Draw UI Panels (Toolbar and Inspector sidebar)
    # Toolbar panel
    toolbar_rect = pygame.Rect(0, 0, width, TOOLBAR_HEIGHT)
    pygame.draw.rect(screen, UITheme.BG_DARK, toolbar_rect, border_radius=0)
    pygame.draw.rect(screen, UITheme.BORDER, toolbar_rect, width=1)
    
    # Title Text as Logo on the left of Toolbar
    title_font = pygame.font.SysFont(UITheme.FONT_NAME, 18, bold=True)
    title_surf = title_font.render("MARBLE PHYSICS LAB", True, UITheme.ACCENT_CYAN)
    title_rect = title_surf.get_rect(midleft=(15, TOOLBAR_HEIGHT / 2.0))
    screen.blit(title_surf, title_rect)
    
    # Left tools menu header/background panel (toolbar left border)
    tools_menu_height = 80 + len(left_tools) * 40
    tools_panel_rect = pygame.Rect(0, TOOLBAR_HEIGHT, 160, tools_menu_height - TOOLBAR_HEIGHT)
    pygame.draw.rect(screen, UITheme.BG_DARK, tools_panel_rect, border_radius=0)
    pygame.draw.rect(screen, UITheme.BORDER, tools_panel_rect, width=1)
    
    # Draw Toolbar buttons
    tooltip_to_draw = None
    for btn in buttons:
        tooltip = btn.draw(screen, font_medium)
        if tooltip:
            tooltip_to_draw = tooltip
            
    # Draw Drawing Tool buttons
    for t_name, btn in tool_buttons:
        tooltip = btn.draw(screen, font_medium)
        if tooltip:
            tooltip_to_draw = tooltip
            
    # Draw Inspector sidebar
    editor.draw_inspector(screen, font_medium, sidebar_rect)
    
    # F. Draw floating REC indicator HUD if recording is active
    if is_recording:
        rec_x = width // 2 - 60
        rec_y = TOOLBAR_HEIGHT + 15
        rec_w, rec_h = 120, 30
        
        # Semi-transparent background container
        rec_bg = pygame.Surface((rec_w, rec_h), pygame.SRCALPHA)
        pygame.draw.rect(rec_bg, (15, 15, 20, 200), (0, 0, rec_w, rec_h), border_radius=6)
        pygame.draw.rect(rec_bg, (255, 50, 50, 100), (0, 0, rec_w, rec_h), width=1, border_radius=6)
        screen.blit(rec_bg, (rec_x, rec_y))
        
        # Pulsing recording dot
        alpha = int(127 + 128 * math.sin(pygame.time.get_ticks() * 0.007))
        pygame.draw.circle(screen, (255, 50, 50), (rec_x + 20, rec_y + 15), 5)
        
        # Pulse outline glow
        pulse_surf = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(pulse_surf, (255, 50, 50, alpha // 3), (12, 12), 10)
        screen.blit(pulse_surf, (rec_x + 8, rec_y + 3))
        
        # Time counter text
        rec_time = recording_frame_count / 60.0
        rec_txt_surf = font_medium.render(f"REC {rec_time:.1f}s", True, (255, 255, 255))
        screen.blit(rec_txt_surf, (rec_x + 35, rec_y + 6))
        
    # G. Draw tooltips over everything else
    if tooltip_to_draw:
        Tooltip.draw(screen, tooltip_to_draw, pygame.mouse.get_pos(), font_medium)
        
    # Flip display
    pygame.display.flip()
    
    # Lock loop to 60 FPS
    clock.tick(60)
