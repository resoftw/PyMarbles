import pygame
import sys
import os
import math
import random
import subprocess
import threading
from camera import Camera
from physics_manager import PhysicsManager
from map_manager import MapManager
from video_exporter import VideoExporter
from editor import Editor
from simulation import Simulation
from ui import UITheme, Button, Slider, Tooltip, draw_neon_line, draw_neon_circle
from sound_manager import SoundManager

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
export_filepath = "D:/Projects/2026/Python/Marbles/exports/marble_race_recording.mp4"

# Set up UI Buttons in Toolbar
buttons = []
def build_ui():
    buttons.clear()
    
    # 1. State Control (Offset to x=240 to clear left side for brand logo title)
    buttons.append(Button(240, 12, 90, 36, "SIMULATE" if not simulation.running else "EDIT", tooltip="Toggle between Edit and Race simulation mode", action_callback=toggle_play_state))
    
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
    
    # 5. Recorder
    rec_text = "STOP REC" if is_recording else "RECORD MP4"
    buttons.append(Button(1064, 12, 110, 36, rec_text, tooltip="Record real-time video and audio", action_callback=toggle_recording))
    
    # 6. Grid snap & Follow camera
    snap_text = "SNAP: ON" if editor.grid_snap else "SNAP: OFF"
    buttons.append(Button(1182, 12, 85, 36, snap_text, tooltip="Toggle Grid Snapping", action_callback=toggle_grid_snap))
    
    cam_text = "CAM: FOLLOW" if simulation.camera_mode == "leader" else "CAM: FREE"
    buttons.append(Button(1275, 12, 100, 36, cam_text, tooltip="Toggle follow leading marble", action_callback=toggle_camera_mode))
    
    # 7. Quit button
    buttons.append(Button(width - 65, 12, 50, 36, "QUIT", tooltip="Exit the application", action_callback=lambda: sys.exit(0)))

def toggle_play_state():
    global is_recording
    if simulation.running:
        if is_recording:
            stop_realtime_recording()
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

def generate_random_map():
    global is_recording
    if is_recording:
        stop_realtime_recording()
    editor.save_undo_state()
    MapManager.generate_random_map(physics)
    camera.x, camera.y = 0.0, 0.0
    editor.selected_entity = None

def load_preset_map(name):
    global is_recording
    if is_recording:
        stop_realtime_recording()
    editor.save_undo_state()
    MapManager.load_preset(physics, name)
    camera.x, camera.y = 0.0, 0.0
    editor.selected_entity = None

def save_map():
    MapManager.save_map(physics, "D:/Projects/2026/Python/Marbles/maps/map.json")
    print("Map saved to maps/map.json")

def load_map():
    global is_recording
    if is_recording:
        stop_realtime_recording()
    editor.save_undo_state()
    if MapManager.load_map(physics, "D:/Projects/2026/Python/Marbles/maps/map.json"):
        camera.x, camera.y = 0.0, 0.0
        editor.selected_entity = None
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

def merge_audio_video_async(temp_video, temp_audio, final_video):
    def run_merge():
        print("Merging audio and video in background...")
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
                if os.path.exists(temp_video):
                    try:
                        os.remove(temp_video)
                    except Exception as e:
                        print(f"Error removing temp video file: {e}")
                if os.path.exists(temp_audio):
                    try:
                        os.remove(temp_audio)
                    except Exception as e:
                        print(f"Error removing temp audio file: {e}")
            else:
                print(f"FFmpeg merge failed with return code {result.returncode}")
                print(f"FFmpeg stderr: {result.stderr}")
        except Exception as e:
            print(f"Error during audio/video merge: {e}")
            
    thread = threading.Thread(target=run_merge)
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
    temp_video_path = "D:/Projects/2026/Python/Marbles/exports/temp_video.mp4"
    # Ensure export folder exists
    os.makedirs("D:/Projects/2026/Python/Marbles/exports", exist_ok=True)
    
    success = video_exporter.start_recording(temp_video_path, width, height, fps=60)
    if success:
        is_recording = True
        recording_frame_count = 0
        print("Real-time recording started.")
    else:
        print("Failed to start real-time video recording.")
        
    build_ui()

def stop_realtime_recording():
    global is_recording, recording_frame_count
    if not is_recording:
        return
        
    is_recording = False
    
    # 1. Stop video exporter
    video_exporter.stop_recording()
    
    # 2. Stop sound manager recording
    temp_video_path = "D:/Projects/2026/Python/Marbles/exports/temp_video.mp4"
    temp_audio_path = "D:/Projects/2026/Python/Marbles/exports/temp_audio.wav"
    final_video_path = "D:/Projects/2026/Python/Marbles/exports/marble_race_recording.mp4"
    
    duration_sec = recording_frame_count / 60.0
    SoundManager.get_instance().stop_recording(temp_audio_path, duration_sec)
    
    # 3. Stop simulation
    simulation.stop()
    
    # 4. Merge audio and video asynchronously
    merge_audio_video_async(temp_video_path, temp_audio_path, final_video_path)
    
    build_ui()

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
                else:
                    editor.handle_inspector_click(m_pos)
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
    SoundManager.get_instance().camera_pos = (camera.x, camera.y)
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
