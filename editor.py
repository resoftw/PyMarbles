import pygame
import math
from ui import UITheme, Button, Slider, Tooltip, draw_neon_line, draw_neon_circle

# Output formats available for the render frame: label -> (width_px, height_px)
RENDER_FORMATS = {
    "16:9":  (1920, 1080),
    "9:16":  (1080, 1920),
    "1:1":   (1080, 1080),
    "4:3":   (1440, 1080),
    "21:9":  (2560, 1080),
}
FORMAT_ORDER = ["16:9", "9:16", "1:1", "4:3", "21:9"]

def render_frame_size(frame):
    """World-space (width, height) of a render frame; width follows the format aspect."""
    ow, oh = RENDER_FORMATS[frame["format"]]
    h = frame["height"]
    return h * (ow / float(oh)), h

def render_frame_corners(frame):
    """Returns the 4 world-space corners of the (possibly rotated) render frame:
    [top-right, top-left, bottom-left, bottom-right]."""
    cx, cy = frame["pos"]
    w, h = render_frame_size(frame)
    a = frame["angle"]
    rx, ry = math.cos(a), math.sin(a)        # local +x axis (world)
    ux, uy = -math.sin(a), math.cos(a)       # local +y axis (world)
    hw, hh = w / 2.0, h / 2.0
    return [
        (cx + rx * hw + ux * hh, cy + ry * hw + uy * hh),
        (cx - rx * hw + ux * hh, cy - ry * hw + uy * hh),
        (cx - rx * hw - ux * hh, cy - ry * hw - uy * hh),
        (cx + rx * hw - ux * hh, cy + ry * hw - uy * hh),
    ]

class Editor:
    def __init__(self, physics_manager, camera):
        self.physics = physics_manager
        self.camera = camera
        
        # Current active drawing tool
        # "select", "wall", "box", "booster", "portal", "spawner", "finish", "eraser"
        self.active_tool = "select"
        
        # Grid snap setting
        self.grid_snap = False
        self.grid_size = 0.5 # world units
        
        # Editing states
        self.selected_entity = None # (type_str, obj_ref)
        self.drawing = False
        self.draw_start = None # world coord (wx, wy)
        self.portal_start = None # world coord for portal a

        # Render guide frame (Blender-style render region). Single optional dict:
        # {'pos': (x,y), 'height': world_h, 'angle': rad, 'format': '16:9'}
        self.render_frame = None
        
        # Select dragging variables for Moving/Scaling/Rotating objects interactively
        self.dragging_entity = None
        self.active_handle = None   # None, "p1", "p2", "pos_a", "pos_b", "center", "body", "rotate", "corner_0", "corner_1", "corner_2", "corner_3"
        self.last_mouse_world = None
        
        # Undo/Redo stacks
        self.undo_stack = []
        self.redo_stack = []
        
        # Properties sliders
        self.sliders = {}
        self.setup_sliders()
        
    def setup_sliders(self):
        # Create standard sliders for the Inspector Panel
        # Slider(x, y, width, min_val, max_val, initial_val, label)
        self.sliders["friction"] = Slider(0, 0, 260, 0.0, 1.0, 0.5, "Friction")
        self.sliders["elasticity"] = Slider(0, 0, 260, 0.0, 1.5, 0.8, "Elasticity (Bounciness)")
        self.sliders["mass"] = Slider(0, 0, 260, 0.1, 50.0, 1.0, "Mass (Dynamic only)")
        self.sliders["booster_force"] = Slider(0, 0, 260, 10.0, 300.0, 80.0, "Booster Force")
        self.sliders["spawner_rate"] = Slider(0, 0, 260, 0.02, 2.0, 0.15, "Spawn Interval (s)")
        self.sliders["spawner_count"] = Slider(0, 0, 260, 1, 200, 30, "Marble Count", format_str="{:.0f}")
        
        # Box custom sliders
        self.sliders["box_angle"] = Slider(0, 0, 260, 0.0, 360.0, 0.0, "Rotation Angle (deg)", format_str="{:.0f}")
        self.sliders["box_width"] = Slider(0, 0, 260, 0.2, 15.0, 2.0, "Width")
        self.sliders["box_height"] = Slider(0, 0, 260, 0.2, 15.0, 2.0, "Height")

        # Conveyor, Escalator, Elevator, Seesaw, Spinner custom sliders
        self.sliders["conveyor_speed"] = Slider(0, 0, 260, -20.0, 20.0, 6.0, "Speed")
        self.sliders["escalator_step"] = Slider(0, 0, 260, 0.2, 3.0, 0.8, "Escalator Step Size")
        self.sliders["elevator_speed"] = Slider(0, 0, 260, 0.5, 15.0, 3.0, "Elevator Speed")
        self.sliders["elevator_travel"] = Slider(0, 0, 260, 2.0, 30.0, 8.0, "Elevator Travel")
        self.sliders["seesaw_length"] = Slider(0, 0, 260, 2.0, 15.0, 6.0, "Seesaw Length")
        self.sliders["spinner_speed"] = Slider(0, 0, 260, -15.0, 15.0, 2.0, "Spinner Speed (0 for Passive)")
        self.sliders["spinner_blades"] = Slider(0, 0, 260, 2.0, 8.0, 4.0, "Blade Count", format_str="{:.0f}")

    def snap_point(self, pos):
        """Snaps world coordinate pos to grid if snap is enabled."""
        if not self.grid_snap:
            return pos
        x, y = pos
        snapped_x = round(x / self.grid_size) * self.grid_size
        snapped_y = round(y / self.grid_size) * self.grid_size
        return snapped_x, snapped_y

    def handle_mouse_down(self, pos, button):
        """Called when mouse button is clicked in the main sandbox area."""
        if button == 1: # Left Click
            world_pos = self.camera.screen_to_world(pos)
            world_pos = self.snap_point(world_pos)
            
            if self.active_tool == "select":
                # Check click near endpoints/handles of the currently selected entity first (highest priority)
                if self.selected_entity:
                    handle = self.get_handle_under_mouse(world_pos)
                    if handle:
                        self.active_handle = handle
                        self.dragging_entity = self.selected_entity
                        self.last_mouse_world = world_pos
                        self.save_undo_state()
                        return
                
                # If no handle clicked, find new entity to select
                entity = self.find_entity_at(world_pos)
                if entity:
                    self.selected_entity = entity
                    self.sync_sliders_with_selected()
                    
                    # Default handle is moving the entire object
                    self.dragging_entity = entity
                    self.active_handle = "body" if entity[0] in ["wall", "booster", "finish", "portal_a", "portal_b"] else "center"
                    self.last_mouse_world = world_pos
                    self.save_undo_state()
                else:
                    self.selected_entity = None
                    self.active_handle = None
            
            elif self.active_tool == "eraser":
                entity = self.find_entity_at(world_pos)
                if entity:
                    self.save_undo_state()
                    self.delete_entity(entity)
                    if self.selected_entity == entity:
                        self.selected_entity = None
            elif self.active_tool in ["wall", "box", "booster", "finish", "conveyor", "escalator", "renderframe"]:
                self.drawing = True
                self.draw_start = world_pos
            elif self.active_tool == "spawner":
                self.save_undo_state()
                self.physics.add_spawner(world_pos, rate=0.15, count=30)
            elif self.active_tool == "portal":
                if self.portal_start is None:
                    # Place first portal
                    self.portal_start = world_pos
                else:
                    # Place second portal and connect
                    self.save_undo_state()
                    self.physics.add_portal(self.portal_start, world_pos)
                    self.portal_start = None
            elif self.active_tool == "elevator":
                self.save_undo_state()
                self.physics.add_elevator(world_pos)
            elif self.active_tool == "seesaw":
                self.save_undo_state()
                self.physics.add_seesaw(world_pos)
            elif self.active_tool == "spinner":
                self.save_undo_state()
                self.physics.add_spinner(world_pos)

    def handle_mouse_up(self, pos, button):
        """Called when mouse button is released in the main sandbox area."""
        if button == 1:
            if self.drawing:
                world_pos = self.camera.screen_to_world(pos)
                world_pos = self.snap_point(world_pos)
                self.drawing = False
                
                if self.draw_start is None:
                    return
                    
                dx = world_pos[0] - self.draw_start[0]
                dy = world_pos[1] - self.draw_start[1]
                dist = math.hypot(dx, dy)
                
                if dist > 0.1: # prevent micro-objects
                    self.save_undo_state()
                    if self.active_tool == "wall":
                        self.physics.add_wall(self.draw_start, world_pos)
                    elif self.active_tool == "booster":
                        self.physics.add_booster(self.draw_start, world_pos, force_strength=80.0)
                    elif self.active_tool == "finish":
                        self.physics.add_finish_line(self.draw_start, world_pos)
                    elif self.active_tool == "conveyor":
                        self.physics.add_conveyor(self.draw_start, world_pos)
                    elif self.active_tool == "escalator":
                        self.physics.add_escalator(self.draw_start, world_pos)
                    elif self.active_tool == "box":
                        cx = (self.draw_start[0] + world_pos[0]) / 2.0
                        cy = (self.draw_start[1] + world_pos[1]) / 2.0
                        width = abs(dx)
                        height = abs(dy)
                        width = max(width, 0.2)
                        height = max(height, 0.2)
                        self.physics.add_box((cx, cy), width, height, is_dynamic=False)
                    elif self.active_tool == "renderframe":
                        cx = (self.draw_start[0] + world_pos[0]) / 2.0
                        cy = (self.draw_start[1] + world_pos[1]) / 2.0
                        fmt = self.render_frame["format"] if self.render_frame else "16:9"
                        self.render_frame = {
                            "pos": (cx, cy),
                            "height": max(2.0, abs(dy)),
                            "angle": 0.0,
                            "format": fmt,
                        }
                        # Select it and switch to the select tool for immediate transform
                        self.selected_entity = ("render_frame", self.render_frame)
                        self.active_tool = "select"

            # Reset select dragging states
            self.dragging_entity = None
            self.active_handle = None
            self.last_mouse_world = None

    def get_handle_under_mouse(self, world_pos):
        """Checks if world_pos is near any interactive handle of the selected entity."""
        if not self.selected_entity:
            return None
            
        wx, wy = world_pos
        tol = 0.5 # click tolerance in world space
        
        type_str, obj = self.selected_entity
        
        if type_str in ["wall", "booster", "finish", "conveyor", "escalator"]:
            p1 = obj.a if type_str == "wall" else obj['p1']
            p2 = obj.b if type_str == "wall" else obj['p2']
            if math.hypot(wx - p1[0], wy - p1[1]) < tol:
                return "p1"
            if math.hypot(wx - p2[0], wy - p2[1]) < tol:
                return "p2"
            if self._point_to_seg_dist(world_pos, p1, p2) < tol:
                return "body"
                
        elif type_str in ["portal_a", "portal_b"]:
            portal_data = obj
            if math.hypot(wx - portal_data['pos_a'][0], wy - portal_data['pos_a'][1]) < tol:
                return "pos_a"
            if math.hypot(wx - portal_data['pos_b'][0], wy - portal_data['pos_b'][1]) < tol:
                return "pos_b"
            if math.hypot(wx - portal_data['pos_a'][0], wy - portal_data['pos_a'][1]) < portal_data['radius']:
                return "body"
            if math.hypot(wx - portal_data['pos_b'][0], wy - portal_data['pos_b'][1]) < portal_data['radius']:
                return "body"
                
        elif type_str == "spawner":
            if math.hypot(wx - obj['pos'][0], wy - obj['pos'][1]) < tol:
                return "center"

        elif type_str in ["elevator", "seesaw", "spinner"]:
            if math.hypot(wx - obj['pos'][0], wy - obj['pos'][1]) < tol:
                return "center"
                
        elif type_str == "box":
            cx, cy = obj.body.position.x, obj.body.position.y
            
            # Center move handle
            if math.hypot(wx - cx, wy - cy) < tol:
                return "center"
                
            # Rotation handle above the box
            a = obj.body.angle
            h = obj.height
            ux, uy = -math.sin(a), math.cos(a) # pointing up relative to box
            rot_x = cx + ux * (h/2.0 + 1.2)
            rot_y = cy + uy * (h/2.0 + 1.2)
            if math.hypot(wx - rot_x, wy - rot_y) < tol:
                return "rotate"
                
            # 4 Corners (scale handles)
            w = obj.width
            rx, ry = math.cos(a), math.sin(a)
            corners = [
                (cx + rx * (w/2.0) + ux * (h/2.0), cy + ry * (w/2.0) + uy * (h/2.0)), # top-right
                (cx - rx * (w/2.0) + ux * (h/2.0), cy - ry * (w/2.0) + uy * (h/2.0)), # top-left
                (cx - rx * (w/2.0) - ux * (h/2.0), cy - ry * (w/2.0) - uy * (h/2.0)), # bottom-left
                (cx + rx * (w/2.0) - ux * (h/2.0), cy + ry * (w/2.0) - uy * (h/2.0))  # bottom-right
            ]
            for i, c in enumerate(corners):
                if math.hypot(wx - c[0], wy - c[1]) < tol:
                    return f"corner_{i}"
                    
            # Check inside the box body as moving handle fallback
            if math.hypot(wx - cx, wy - cy) < max(w, h):
                return "center"

        elif type_str == "render_frame":
            cx, cy = obj["pos"]
            a = obj["angle"]
            w, h = render_frame_size(obj)
            ux, uy = -math.sin(a), math.cos(a)  # local +y
            # Rotation handle above the top edge
            rot_x = cx + ux * (h / 2.0 + 1.2)
            rot_y = cy + uy * (h / 2.0 + 1.2)
            if math.hypot(wx - rot_x, wy - rot_y) < tol:
                return "rotate"
            # 4 corners (uniform scale)
            for i, c in enumerate(render_frame_corners(obj)):
                if math.hypot(wx - c[0], wy - c[1]) < tol:
                    return f"corner_{i}"
            # Center move handle
            if math.hypot(wx - cx, wy - cy) < tol:
                return "center"

        return None

    def handle_mouse_move(self, pos):
        """Interactive drag to translate, rotate, or scale entities in sandbox."""
        if not self.selected_entity or not self.active_handle or not self.last_mouse_world:
            return False
            
        world_pos = self.camera.screen_to_world(pos)
        
        # Grid snap if moving or scaling (do not grid snap rotation)
        if self.active_handle != "rotate":
            world_pos = self.snap_point(world_pos)
            
        dx = world_pos[0] - self.last_mouse_world[0]
        dy = world_pos[1] - self.last_mouse_world[1]
        
        if dx == 0 and dy == 0:
            return False
            
        type_str, obj = self.selected_entity
        
        # Render frame transforms (move / rotate / uniform scale) handled up front
        if type_str == "render_frame":
            cx, cy = obj["pos"]
            if self.active_handle in ("center", "body"):
                obj["pos"] = (cx + dx, cy + dy)
            elif self.active_handle == "rotate":
                mouse_angle = math.atan2(world_pos[1] - cy, world_pos[0] - cx)
                obj["angle"] = mouse_angle - math.pi / 2.0
            elif self.active_handle.startswith("corner_"):
                # Project mouse into frame-local space; the local Y sets the height
                a = obj["angle"]
                rxw, ryw = world_pos[0] - cx, world_pos[1] - cy
                local_y = -rxw * math.sin(a) + ryw * math.cos(a)
                obj["height"] = max(1.0, abs(local_y) * 2.0)
            self.last_mouse_world = world_pos
            return True

        if self.active_handle == "center" or self.active_handle == "body":
            # Translate entire object
            if type_str == "spawner":
                obj['pos'] = (obj['pos'][0] + dx, obj['pos'][1] + dy)
            elif type_str in ["portal_a", "portal_b"]:
                obj['pos_a'] = (obj['pos_a'][0] + dx, obj['pos_a'][1] + dy)
                obj['pos_b'] = (obj['pos_b'][0] + dx, obj['pos_b'][1] + dy)
                obj['shape_a'].body.position = obj['pos_a']
                obj['shape_b'].body.position = obj['pos_b']
            elif type_str == "wall":
                new_a = (obj.a[0] + dx, obj.a[1] + dy)
                new_b = (obj.b[0] + dx, obj.b[1] + dy)
                obj.unsafe_set_endpoints(new_a, new_b)
                self.physics.space.reindex_shape(obj)
            elif type_str == "booster":
                obj['p1'] = (obj['p1'][0] + dx, obj['p1'][1] + dy)
                obj['p2'] = (obj['p2'][0] + dx, obj['p2'][1] + dy)
                obj['shape'].unsafe_set_endpoints(obj['p1'], obj['p2'])
                self.physics.space.reindex_shape(obj['shape'])
                p1, p2 = obj['p1'], obj['p2']
                length = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
                obj['direction'] = ((p2[0]-p1[0])/length, (p2[1]-p1[1])/length) if length > 0 else (1.0, 0.0)
            elif type_str in ["conveyor", "escalator"]:
                obj['p1'] = (obj['p1'][0] + dx, obj['p1'][1] + dy)
                obj['p2'] = (obj['p2'][0] + dx, obj['p2'][1] + dy)
                obj['shape'].unsafe_set_endpoints(obj['p1'], obj['p2'])
                self.physics.space.reindex_shape(obj['shape'])
                p1, p2 = obj['p1'], obj['p2']
                length = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
                obj['direction'] = ((p2[0]-p1[0])/length, (p2[1]-p1[1])/length) if length > 0 else (1.0, 0.0)
                if type_str == "escalator":
                    self.physics.recreate_escalator_steps(obj)
            elif type_str == "elevator":
                obj['pos'] = (obj['pos'][0] + dx, obj['pos'][1] + dy)
                obj['body'].position = obj['pos']
                travel = obj['end_y'] - obj['start_y']
                obj['start_y'] = obj['pos'][1]
                obj['end_y'] = obj['pos'][1] + travel
                self.physics.space.reindex_shape(obj['shape'])
            elif type_str in ["seesaw", "spinner"]:
                obj['pos'] = (obj['pos'][0] + dx, obj['pos'][1] + dy)
                obj['body'].position = obj['pos']
                obj['pivot_body'].position = obj['pos']
                if type_str == "seesaw":
                    self.physics.space.reindex_shape(obj['shape'])
                else:
                    for s in obj['shapes']:
                        self.physics.space.reindex_shape(s)
            elif type_str == "finish":
                obj['p1'] = (obj['p1'][0] + dx, obj['p1'][1] + dy)
                obj['p2'] = (obj['p2'][0] + dx, obj['p2'][1] + dy)
                obj['shape'].unsafe_set_endpoints(obj['p1'], obj['p2'])
                self.physics.space.reindex_shape(obj['shape'])
            elif type_str == "box":
                obj.body.position = (obj.body.position[0] + dx, obj.body.position[1] + dy)
                self.physics.space.reindex_shape(obj)
                
        elif self.active_handle == "p1":
            if type_str == "wall":
                obj.unsafe_set_endpoints(world_pos, obj.b)
                self.physics.space.reindex_shape(obj)
            elif type_str == "booster":
                obj['p1'] = world_pos
                obj['shape'].unsafe_set_endpoints(obj['p1'], obj['p2'])
                self.physics.space.reindex_shape(obj['shape'])
                p1, p2 = obj['p1'], obj['p2']
                length = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
                obj['direction'] = ((p2[0]-p1[0])/length, (p2[1]-p1[1])/length) if length > 0 else (1.0, 0.0)
            elif type_str in ["conveyor", "escalator"]:
                obj['p1'] = world_pos
                obj['shape'].unsafe_set_endpoints(obj['p1'], obj['p2'])
                self.physics.space.reindex_shape(obj['shape'])
                p1, p2 = obj['p1'], obj['p2']
                length = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
                obj['direction'] = ((p2[0]-p1[0])/length, (p2[1]-p1[1])/length) if length > 0 else (1.0, 0.0)
                if type_str == "escalator":
                    self.physics.recreate_escalator_steps(obj)
            elif type_str == "finish":
                obj['p1'] = world_pos
                obj['shape'].unsafe_set_endpoints(obj['p1'], obj['p2'])
                self.physics.space.reindex_shape(obj['shape'])
                
        elif self.active_handle == "p2":
            if type_str == "wall":
                obj.unsafe_set_endpoints(obj.a, world_pos)
                self.physics.space.reindex_shape(obj)
            elif type_str == "booster":
                obj['p2'] = world_pos
                obj['shape'].unsafe_set_endpoints(obj['p1'], obj['p2'])
                self.physics.space.reindex_shape(obj['shape'])
                p1, p2 = obj['p1'], obj['p2']
                length = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
                obj['direction'] = ((p2[0]-p1[0])/length, (p2[1]-p1[1])/length) if length > 0 else (1.0, 0.0)
            elif type_str in ["conveyor", "escalator"]:
                obj['p2'] = world_pos
                obj['shape'].unsafe_set_endpoints(obj['p1'], obj['p2'])
                self.physics.space.reindex_shape(obj['shape'])
                p1, p2 = obj['p1'], obj['p2']
                length = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
                obj['direction'] = ((p2[0]-p1[0])/length, (p2[1]-p1[1])/length) if length > 0 else (1.0, 0.0)
                if type_str == "escalator":
                    self.physics.recreate_escalator_steps(obj)
            elif type_str == "finish":
                obj['p2'] = world_pos
                obj['shape'].unsafe_set_endpoints(obj['p1'], obj['p2'])
                self.physics.space.reindex_shape(obj['shape'])
                
        elif self.active_handle == "pos_a":
            obj['pos_a'] = world_pos
            obj['shape_a'].body.position = obj['pos_a']
        elif self.active_handle == "pos_b":
            obj['pos_b'] = world_pos
            obj['shape_b'].body.position = obj['pos_b']
            
        elif self.active_handle == "rotate":
            # Angle pointing from box center to mouse position
            cx, cy = obj.body.position.x, obj.body.position.y
            mouse_angle = math.atan2(world_pos[1] - cy, world_pos[0] - cx)
            # Subtract 90 degrees (pi/2) because rotation handle is aligned with local Y axis
            obj.body.angle = mouse_angle - math.pi / 2.0
            self.physics.space.reindex_shape(obj)
            
        elif self.active_handle.startswith("corner_"):
            # Dragging corner scales the box width and height relative to center
            local_mouse = obj.body.world_to_local(world_pos)
            new_w = abs(local_mouse.x) * 2.0
            new_h = abs(local_mouse.y) * 2.0
            new_w = max(0.2, min(15.0, new_w))
            new_h = max(0.2, min(15.0, new_h))
            
            resized_shape = self.physics.resize_box(obj, new_w, new_h)
            self.selected_entity = ("box", resized_shape)
            
        self.last_mouse_world = world_pos
        self.sync_sliders_with_selected() # sync inspectors during drag
        return True

    def draw_previews(self, surface):
        """Draws previews of shapes being placed currently."""
        if self.drawing and self.draw_start:
            # Draw line previews
            m_pos = pygame.mouse.get_pos()
            m_world = self.camera.screen_to_world(m_pos)
            m_world = self.snap_point(m_world)
            
            if self.active_tool == "wall":
                draw_neon_line(surface, self.draw_start, m_world, (200, 200, 200), 2, self.camera)
            elif self.active_tool == "booster":
                draw_neon_line(surface, self.draw_start, m_world, (0, 255, 100, 150), 4, self.camera)
            elif self.active_tool == "conveyor":
                draw_neon_line(surface, self.draw_start, m_world, (0, 180, 255, 150), 4, self.camera)
            elif self.active_tool == "escalator":
                draw_neon_line(surface, self.draw_start, m_world, (255, 100, 0, 150), 4, self.camera)
            elif self.active_tool == "finish":
                draw_neon_line(surface, self.draw_start, m_world, (255, 255, 255, 150), 3, self.camera)
            elif self.active_tool == "box":
                # Draw box preview outline
                x1, y1 = self.camera.world_to_screen(self.draw_start)
                x2, y2 = self.camera.world_to_screen(m_world)
                rect = pygame.Rect(min(x1, x2), min(y1, y2), abs(x1 - x2), abs(y1 - y2))
                pygame.draw.rect(surface, (200, 100, 200), rect, width=1)
                
        # Draw portal starting preview
        if self.portal_start:
            draw_neon_circle(surface, self.portal_start, 0.6, (255, 100, 0), width=2, camera=self.camera)
            # Draw line to mouse
            m_pos = pygame.mouse.get_pos()
            m_world = self.camera.screen_to_world(m_pos)
            draw_neon_line(surface, self.portal_start, m_world, (255, 150, 0, 100), 1, self.camera)

    def draw_grid(self, surface):
        """Draws editor grid lines if snap is enabled."""
        if not self.grid_snap:
            return
            
        screen_w, screen_h = surface.get_size()
        w_min = self.camera.screen_to_world((0, screen_h))
        w_max = self.camera.screen_to_world((screen_w, 0))
        
        start_x = math.floor(w_min[0] / self.grid_size) * self.grid_size
        end_x = math.ceil(w_max[0] / self.grid_size) * self.grid_size
        start_y = math.floor(w_min[1] / self.grid_size) * self.grid_size
        end_y = math.ceil(w_max[1] / self.grid_size) * self.grid_size
        
        grid_color = (35, 45, 60)
        
        # Vertical grid lines
        x = start_x
        while x <= end_x:
            sx, _ = self.camera.world_to_screen((x, 0))
            if 0 <= sx < screen_w:
                pygame.draw.line(surface, grid_color, (sx, 0), (sx, screen_h), 1)
            x += self.grid_size
            
        # Horizontal grid lines
        y = start_y
        while y <= end_y:
            _, sy = self.camera.world_to_screen((0, y))
            if 0 <= sy < screen_h:
                pygame.draw.line(surface, grid_color, (0, sy), (screen_w, sy), 1)
            y += self.grid_size

    def draw_handles(self, surface):
        """Draws Figma-like visual screen handles (Move crosshair, Rotate circle, Scale vertices/corners)."""
        if not self.selected_entity or self.active_tool != "select":
            return
            
        type_str, obj = self.selected_entity
        handle_color = (0, 255, 255) # Cyan
        rot_handle_color = (255, 0, 128) # Glowing Magenta
        
        def draw_vertex_circle(pos, color=handle_color, radius=6):
            scr_pos = self.camera.world_to_screen(pos)
            pygame.draw.circle(surface, (255, 255, 255), scr_pos, radius + 2)
            pygame.draw.circle(surface, color, scr_pos, radius)
            
        if type_str in ["wall", "booster", "finish", "conveyor", "escalator"]:
            p1 = obj.a if type_str == "wall" else obj['p1']
            p2 = obj.b if type_str == "wall" else obj['p2']
            draw_vertex_circle(p1)
            draw_vertex_circle(p2)
            
        elif type_str in ["portal_a", "portal_b"]:
            draw_vertex_circle(obj['pos_a'])
            draw_vertex_circle(obj['pos_b'])
            
        elif type_str in ["spawner", "elevator", "seesaw", "spinner"]:
            draw_vertex_circle(obj['pos'])
            
        elif type_str == "box":
            cx, cy = obj.body.position.x, obj.body.position.y
            a = obj.body.angle
            w, h = obj.width, obj.height
            rx, ry = math.cos(a), math.sin(a)
            ux, uy = -math.sin(a), math.cos(a)
            
            # 1. Rotation handle connector line & circle
            rot_x = cx + ux * (h/2.0 + 1.2)
            rot_y = cy + uy * (h/2.0 + 1.2)
            
            scr_center = self.camera.world_to_screen((cx, cy))
            scr_rot = self.camera.world_to_screen((rot_x, rot_y))
            pygame.draw.line(surface, rot_handle_color, scr_center, scr_rot, 1)
            draw_vertex_circle((rot_x, rot_y), color=rot_handle_color, radius=5)
            
            # 2. Four Scale Corners
            corners = [
                (cx + rx * (w/2.0) + ux * (h/2.0), cy + ry * (w/2.0) + uy * (h/2.0)), # top-right
                (cx - rx * (w/2.0) + ux * (h/2.0), cy - ry * (w/2.0) + uy * (h/2.0)), # top-left
                (cx - rx * (w/2.0) - ux * (h/2.0), cy - ry * (w/2.0) - uy * (h/2.0)), # bottom-left
                (cx + rx * (w/2.0) - ux * (h/2.0), cy + ry * (w/2.0) - uy * (h/2.0))  # bottom-right
            ]
            for c in corners:
                scr_c = self.camera.world_to_screen(c)
                rect = pygame.Rect(scr_c[0] - 5, scr_c[1] - 5, 10, 10)
                pygame.draw.rect(surface, (255, 255, 255), rect)
                pygame.draw.rect(surface, (255, 180, 0), rect, width=2)
                
            # 3. Center crosshair move handle
            draw_vertex_circle((cx, cy), color=(255, 255, 255), radius=5)
            pygame.draw.circle(surface, (0, 0, 0), scr_center, 2)

        elif type_str == "render_frame":
            cx, cy = obj["pos"]
            a = obj["angle"]
            w, h = render_frame_size(obj)
            ux, uy = -math.sin(a), math.cos(a)
            rot_x = cx + ux * (h / 2.0 + 1.2)
            rot_y = cy + uy * (h / 2.0 + 1.2)
            scr_center = self.camera.world_to_screen((cx, cy))
            scr_rot = self.camera.world_to_screen((rot_x, rot_y))
            pygame.draw.line(surface, rot_handle_color, scr_center, scr_rot, 1)
            draw_vertex_circle((rot_x, rot_y), color=rot_handle_color, radius=5)
            for c in render_frame_corners(obj):
                scr_c = self.camera.world_to_screen(c)
                rect = pygame.Rect(scr_c[0] - 5, scr_c[1] - 5, 10, 10)
                pygame.draw.rect(surface, (255, 255, 255), rect)
                pygame.draw.rect(surface, (255, 180, 0), rect, width=2)
            draw_vertex_circle((cx, cy), color=(255, 255, 255), radius=5)
            pygame.draw.circle(surface, (0, 0, 0), scr_center, 2)

    def draw_render_frame(self, surface):
        """Draws the render guide frame: rotated border, rule-of-thirds, and a label."""
        if not self.render_frame:
            return
        f = self.render_frame
        scr = [self.camera.world_to_screen(c) for c in render_frame_corners(f)]
        selected = self.selected_entity and self.selected_entity[0] == "render_frame"
        col = (0, 255, 200) if selected else (255, 160, 40)

        pygame.draw.polygon(surface, col, scr, width=2)

        tr, tl, bl, br = scr[0], scr[1], scr[2], scr[3]

        def lerp(p, q, t):
            return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)

        for t in (1.0 / 3.0, 2.0 / 3.0):
            pygame.draw.line(surface, col, lerp(tl, tr, t), lerp(bl, br, t), 1)
            pygame.draw.line(surface, col, lerp(tl, bl, t), lerp(tr, br, t), 1)

        ow, oh = RENDER_FORMATS[f["format"]]
        font = pygame.font.SysFont(UITheme.FONT_NAME, 14, bold=True)
        label = font.render(f"RENDER  {f['format']}  {ow}x{oh}", True, col)
        surface.blit(label, (tl[0], tl[1] - 20))

    def find_entity_at(self, world_pos):
        """Finds any editor entity (wall, spawner, booster, etc.) near world_pos."""
        wx, wy = world_pos
        threshold = 0.5 # click tolerance in world units
        
        for spawner in self.physics.spawners:
            dist = math.hypot(wx - spawner['pos'][0], wy - spawner['pos'][1])
            if dist <= 0.8:
                return ("spawner", spawner)
                
        for portal in self.physics.portals:
            dist_a = math.hypot(wx - portal['pos_a'][0], wy - portal['pos_a'][1])
            dist_b = math.hypot(wx - portal['pos_b'][0], wy - portal['pos_b'][1])
            if dist_a <= portal['radius']:
                return ("portal_a", portal)
            if dist_b <= portal['radius']:
                return ("portal_b", portal)
                
        for wall in self.physics.walls:
            if self._point_to_seg_dist(world_pos, wall.a, wall.b) <= threshold:
                return ("wall", wall)
                
        for booster in self.physics.boosters:
            if self._point_to_seg_dist(world_pos, booster['p1'], booster['p2']) <= threshold:
                return ("booster", booster)
                
        for conv in self.physics.conveyors:
            if self._point_to_seg_dist(world_pos, conv['p1'], conv['p2']) <= threshold:
                return ("conveyor", conv)
                
        for esc in self.physics.escalators:
            if self._point_to_seg_dist(world_pos, esc['p1'], esc['p2']) <= threshold:
                return ("escalator", esc)
                
        for elev in self.physics.elevators:
            dist = math.hypot(wx - elev['pos'][0], wy - elev['pos'][1])
            if dist <= max(elev['width'], elev['height']):
                return ("elevator", elev)
                
        for ss in self.physics.seesaws:
            dist = math.hypot(wx - ss['pos'][0], wy - ss['pos'][1])
            if dist <= ss['length'] / 2.0:
                return ("seesaw", ss)
                
        for sp in self.physics.spinners:
            dist = math.hypot(wx - sp['pos'][0], wy - sp['pos'][1])
            if dist <= sp['radius']:
                return ("spinner", sp)
                
        for finish in self.physics.finish_lines:
            if self._point_to_seg_dist(world_pos, finish['p1'], finish['p2']) <= threshold:
                return ("finish", finish)
                
        for box in self.physics.boxes:
            dist = math.hypot(wx - box.body.position[0], wy - box.body.position[1])
            if dist <= max(box.width, box.height):
                return ("box", box)

        # Render frame: only its border is clickable, so objects inside stay selectable
        if self.render_frame:
            corners = render_frame_corners(self.render_frame)
            for i in range(4):
                if self._point_to_seg_dist(world_pos, corners[i], corners[(i + 1) % 4]) <= threshold:
                    return ("render_frame", self.render_frame)

        return None

    def _point_to_seg_dist(self, p, s1, s2):
        px, py = p
        x1, y1 = s1
        x2, y2 = s2
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = ((px - x1) * dx + (py - y1) * dy) / (dx*dx + dy*dy)
        t = max(0.0, min(1.0, t))
        return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

    def delete_entity(self, entity):
        """Removes the entity from physics space and collections."""
        type_str, obj = entity

        if type_str == "render_frame":
            self.render_frame = None
            return

        space = self.physics.space
        
        def safe_remove(*objs):
            import pymunk
            for o in objs:
                if o is None:
                    continue
                if isinstance(o, pymunk.Body):
                    if o in space.bodies:
                        space.remove(o)
                elif isinstance(o, pymunk.Shape):
                    if o in space.shapes:
                        space.remove(o)
                elif isinstance(o, pymunk.Constraint):
                    if o in space.constraints:
                        space.remove(o)

        if type_str == "wall":
            self.physics.walls.remove(obj)
            safe_remove(obj)
        elif type_str == "box":
            self.physics.boxes.remove(obj)
            safe_remove(obj.body, obj)
        elif type_str == "booster":
            self.physics.boosters.remove(obj)
            safe_remove(obj['shape'])
        elif type_str == "conveyor":
            self.physics.conveyors.remove(obj)
            safe_remove(obj['shape'])
        elif type_str == "escalator":
            self.physics.escalators.remove(obj)
            safe_remove(obj['shape'])
            for body, tread, riser in obj.get('steps', []):
                safe_remove(body, tread, riser)
        elif type_str == "elevator":
            self.physics.elevators.remove(obj)
            safe_remove(obj['body'], obj['shape'])
        elif type_str == "seesaw":
            self.physics.seesaws.remove(obj)
            safe_remove(obj['body'], obj['shape'], obj['joint'], obj['limit'], obj.get('motor'))
        elif type_str == "spinner":
            self.physics.spinners.remove(obj)
            safe_remove(obj['body'], obj['joint'], obj.get('motor'))
            for s in obj['shapes']:
                safe_remove(s)
        elif type_str == "portal_a" or type_str == "portal_b":
            self.physics.portals.remove(obj)
            safe_remove(obj['shape_a'].body, obj['shape_a'])
            safe_remove(obj['shape_b'].body, obj['shape_b'])
        elif type_str == "finish":
            self.physics.finish_lines.remove(obj)
            safe_remove(obj['shape'])
        elif type_str == "spawner":
            self.physics.spawners.remove(obj)

    def sync_sliders_with_selected(self):
        """Syncs GUI sliders with properties of the selected entity."""
        if not self.selected_entity:
            return
            
        type_str, obj = self.selected_entity
        if type_str == "wall":
            self.sliders["friction"].value = obj.friction
            self.sliders["elasticity"].value = obj.elasticity
        elif type_str == "box":
            self.sliders["friction"].value = obj.friction
            self.sliders["elasticity"].value = obj.elasticity
            self.sliders["mass"].value = obj.body.mass if obj.is_dynamic else 1.0
            
            deg = math.degrees(obj.body.angle) % 360.0
            self.sliders["box_angle"].value = deg
            self.sliders["box_width"].value = obj.width
            self.sliders["box_height"].value = obj.height
        elif type_str == "booster":
            self.sliders["booster_force"].value = obj["force_strength"]
        elif type_str == "conveyor":
            self.sliders["conveyor_speed"].value = obj["speed"]
        elif type_str == "escalator":
            self.sliders["conveyor_speed"].value = obj["speed"]
            self.sliders["escalator_step"].value = obj.get("step_size", 0.8)
        elif type_str == "elevator":
            self.sliders["elevator_speed"].value = obj["speed"]
            self.sliders["elevator_travel"].value = obj["end_y"] - obj["start_y"]
        elif type_str == "seesaw":
            self.sliders["seesaw_length"].value = obj["length"]
        elif type_str == "spinner":
            self.sliders["spinner_speed"].value = obj["motor_speed"] if obj["is_motorized"] else 0.0
            self.sliders["spinner_blades"].value = obj["num_blades"]
        elif type_str == "spawner":
            self.sliders["spawner_rate"].value = obj["rate"]
            self.sliders["spawner_count"].value = obj["count"]

    def update_selected_properties(self):
        """Updates selected entity's properties from GUI slider values."""
        if not self.selected_entity:
            return
            
        type_str, obj = self.selected_entity
        if type_str == "wall":
            obj.friction = self.sliders["friction"].value
            obj.elasticity = self.sliders["elasticity"].value
        elif type_str == "box":
            obj.friction = self.sliders["friction"].value
            obj.elasticity = self.sliders["elasticity"].value
            
            obj.body.angle = math.radians(self.sliders["box_angle"].value)
            self.physics.space.reindex_shape(obj)
            
            new_w = self.sliders["box_width"].value
            new_h = self.sliders["box_height"].value
            new_w = max(0.2, new_w)
            new_h = max(0.2, new_h)
            
            if abs(new_w - obj.width) > 0.05 or abs(new_h - obj.height) > 0.05:
                resized_shape = self.physics.resize_box(obj, new_w, new_h)
                self.selected_entity = ("box", resized_shape)
                obj = resized_shape
            
            if obj.is_dynamic:
                new_mass = self.sliders["mass"].value
                obj.body.mass = new_mass
                import pymunk
                obj.body.moment = pymunk.moment_for_box(new_mass, (obj.width, obj.height))
        elif type_str == "booster":
            obj["force_strength"] = self.sliders["booster_force"].value
        elif type_str == "conveyor":
            obj["speed"] = self.sliders["conveyor_speed"].value
            obj["shape"].surface_velocity = (obj["speed"], 0.0)
        elif type_str == "escalator":
            new_speed = self.sliders["conveyor_speed"].value
            new_step = self.sliders["escalator_step"].value
            if new_speed != obj["speed"] or new_step != obj.get("step_size", 0.8):
                obj["speed"] = new_speed
                obj["step_size"] = new_step
                self.physics.recreate_escalator_steps(obj)
        elif type_str == "elevator":
            obj["speed"] = self.sliders["elevator_speed"].value
            travel = self.sliders["elevator_travel"].value
            obj["end_y"] = obj["start_y"] + travel
        elif type_str == "seesaw":
            new_len = self.sliders["seesaw_length"].value
            if abs(new_len - obj["length"]) > 0.05:
                obj["length"] = new_len
                body = obj["body"]
                if obj["shape"] in self.physics.space.shapes:
                    self.physics.space.remove(obj["shape"])
                w_half = new_len / 2.0
                h_half = obj["thickness"] / 2.0
                verts = [(-w_half, -h_half), (w_half, -h_half), (w_half, h_half), (-w_half, h_half)]
                new_shape = pymunk.Poly(body, verts)
                new_shape.friction = 0.5
                new_shape.elasticity = 0.2
                new_shape.color = obj["color"]
                new_shape.collision_type = self.physics.COLLISION_SEESAW
                new_shape.custom_data = obj
                obj["shape"] = new_shape
                self.physics.space.add(new_shape)
                
                # Update moment of inertia
                import pymunk
                body.moment = pymunk.moment_for_box(body.mass, (new_len, obj["thickness"]))
        elif type_str == "spinner":
            new_speed = self.sliders["spinner_speed"].value
            new_blades = int(self.sliders["spinner_blades"].value)
            speed_changed = (new_speed != (obj["motor_speed"] if obj["is_motorized"] else 0.0))
            blades_changed = (new_blades != obj["num_blades"])
            if speed_changed or blades_changed:
                space = self.physics.space
                if obj["body"] in space.bodies:
                    space.remove(obj["body"])
                if obj["joint"] in space.constraints:
                    space.remove(obj["joint"])
                for s in obj["shapes"]:
                    if s in space.shapes:
                        space.remove(s)
                if obj["motor"] and obj["motor"] in space.constraints:
                    space.remove(obj["motor"])
                new_sp = self.physics.add_spinner(
                    pos=obj["pos"],
                    radius=obj["radius"],
                    num_blades=new_blades,
                    is_motorized=(new_speed != 0.0),
                    motor_speed=new_speed,
                    color=obj["color"]
                )
                # Remove the newly appended duplicate from spinners list
                self.physics.spinners.pop()
                idx = self.physics.spinners.index(obj)
                self.physics.spinners[idx] = new_sp
                self.selected_entity = ("spinner", new_sp)
        elif type_str == "spawner":
            obj["rate"] = self.sliders["spawner_rate"].value
            obj["count"] = int(self.sliders["spawner_count"].value)

    def save_undo_state(self):
        """Saves current state for undo."""
        state = self._serialize_current_state()
        self.undo_stack.append(state)
        self.redo_stack.clear()
        
    def undo(self):
        if not self.undo_stack:
            return
        current_state = self._serialize_current_state()
        self.redo_stack.append(current_state)
        
        prev_state = self.undo_stack.pop()
        self._deserialize_state(prev_state)
        self.selected_entity = None
        
    def redo(self):
        if not self.redo_stack:
            return
        current_state = self._serialize_current_state()
        self.undo_stack.append(current_state)
        
        next_state = self.redo_stack.pop()
        self._deserialize_state(next_state)
        self.selected_entity = None

    def _serialize_current_state(self):
        """Serializes current map state to a dict."""
        data = {
            "gravity": list(self.physics.space.gravity),
            "walls": [],
            "boxes": [],
            "boosters": [],
            "portals": [],
            "finish_lines": [],
            "spawners": [],
            "conveyors": [],
            "elevators": [],
            "seesaws": [],
            "spinners": [],
            "escalators": []
        }
        for wall in self.physics.walls:
            data["walls"].append({
                "p1": [wall.a[0], wall.a[1]], "p2": [wall.b[0], wall.b[1]],
                "thickness": wall.radius, "friction": wall.friction, "elasticity": wall.elasticity,
                "color": list(wall.color) if hasattr(wall, 'color') else [0, 255, 255]
            })
        for box in self.physics.boxes:
            data["boxes"].append({
                "pos": [box.body.position[0], box.body.position[1]], "width": box.width, "height": box.height,
                "angle": box.body.angle, "is_dynamic": box.is_dynamic, "mass": box.body.mass if box.is_dynamic else 0.0,
                "friction": box.friction, "elasticity": box.elasticity,
                "color": list(box.color) if hasattr(box, 'color') else [255, 0, 255]
            })
        for booster in self.physics.boosters:
            data["boosters"].append({
                "p1": [booster["p1"][0], booster["p1"][1]], "p2": [booster["p2"][0], booster["p2"][1]],
                "force_strength": booster["force_strength"], "color": list(booster["color"])
            })
        for portal in self.physics.portals:
            data["portals"].append({
                "pos_a": [portal["pos_a"][0], portal["pos_a"][1]], "pos_b": [portal["pos_b"][0], portal["pos_b"][1]],
                "radius": portal["radius"], "color": list(portal["color"])
            })
        for finish in self.physics.finish_lines:
            data["finish_lines"].append({
                "p1": [finish["p1"][0], finish["p1"][1]], "p2": [finish["p2"][0], finish["p2"][1]],
                "color": list(finish["color"])
            })
        for spawner in self.physics.spawners:
            data["spawners"].append({
                "pos": [spawner["pos"][0], spawner["pos"][1]], "rate": spawner["rate"], "count": spawner["count"],
                "marble_color": list(spawner["marble_color"]) if spawner["marble_color"] else None
            })
        for conv in self.physics.conveyors:
            data["conveyors"].append({
                "p1": list(conv["p1"]), "p2": list(conv["p2"]), "speed": conv["speed"], "color": list(conv["color"])
            })
        for esc in self.physics.escalators:
            data["escalators"].append({
                "p1": list(esc["p1"]), "p2": list(esc["p2"]), "speed": esc["speed"], "step_size": esc.get("step_size", 0.8), "color": list(esc["color"])
            })
        for elev in self.physics.elevators:
            data["elevators"].append({
                "pos": list(elev["pos"]), "width": elev["width"], "height": elev["height"],
                "travel_distance": elev["end_y"] - elev["start_y"], "speed": elev["speed"], "color": list(elev["color"])
            })
        for ss in self.physics.seesaws:
            data["seesaws"].append({
                "pos": list(ss["pos"]), "length": ss["length"], "thickness": ss["thickness"], "color": list(ss["color"])
            })
        for sp in self.physics.spinners:
            data["spinners"].append({
                "pos": list(sp["pos"]), "radius": sp["radius"], "num_blades": sp["num_blades"],
                "is_motorized": sp["is_motorized"], "motor_speed": sp["motor_speed"], "color": list(sp["color"])
            })
        return data

    def _deserialize_state(self, data):
        """Restores map state from dict."""
        self.physics.clear()
        self.physics.space.gravity = tuple(data["gravity"])
        for w in data["walls"]:
            self.physics.add_wall(tuple(w["p1"]), tuple(w["p2"]), w["thickness"], w["friction"], w["elasticity"], tuple(w["color"]))
        for b in data["boxes"]:
            self.physics.add_box(tuple(b["pos"]), b["width"], b["height"], b["angle"], b["is_dynamic"], b["mass"], b["friction"], b["elasticity"], tuple(b["color"]))
        for b in data["boosters"]:
            self.physics.add_booster(tuple(b["p1"]), tuple(b["p2"]), b["force_strength"], color=tuple(b["color"]))
        for p in data["portals"]:
            self.physics.add_portal(tuple(p["pos_a"]), tuple(p["pos_b"]), p["radius"], tuple(p["color"]))
        for f in data["finish_lines"]:
            self.physics.add_finish_line(tuple(f["p1"]), tuple(f["p2"]), color=tuple(f["color"]))
        for s in data["spawners"]:
            self.physics.add_spawner(tuple(s["pos"]), s["rate"], s["count"], tuple(s["marble_color"]) if s["marble_color"] else None)
        for c in data.get("conveyors", []):
            self.physics.add_conveyor(tuple(c["p1"]), tuple(c["p2"]), c["speed"], color=tuple(c["color"]))
        for esc in data.get("escalators", []):
            self.physics.add_escalator(tuple(esc["p1"]), tuple(esc["p2"]), esc["speed"], step_size=esc.get("step_size", 0.8), color=tuple(esc["color"]))
        for e in data.get("elevators", []):
            self.physics.add_elevator(tuple(e["pos"]), e["width"], e["height"], e["travel_distance"], e["speed"], color=tuple(e["color"]))
        for s in data.get("seesaws", []):
            self.physics.add_seesaw(tuple(s["pos"]), s["length"], s["thickness"], color=tuple(s["color"]))
        for sp in data.get("spinners", []):
            self.physics.add_spinner(tuple(sp["pos"]), sp["radius"], sp["num_blades"], sp["is_motorized"], sp["motor_speed"], color=tuple(sp["color"]))

    def draw_inspector(self, surface, font, sidebar_rect):
        """Draws property inspector details on the sidebar."""
        pygame.draw.rect(surface, UITheme.BG_DARK, sidebar_rect, border_radius=0)
        pygame.draw.rect(surface, UITheme.BORDER, sidebar_rect, width=1)
        
        header_font = pygame.font.SysFont(UITheme.FONT_NAME, 20, bold=True)
        title_surf = header_font.render("INSPECTOR", True, UITheme.ACCENT_CYAN)
        surface.blit(title_surf, (sidebar_rect.x + 20, sidebar_rect.y + 20))
        
        if not self.selected_entity:
            no_sel_surf = font.render("No object selected.", True, UITheme.TEXT_MUTED)
            surface.blit(no_sel_surf, (sidebar_rect.x + 20, sidebar_rect.y + 60))
            return
            
        type_str, obj = self.selected_entity
        self.format_btn_rects = []
        display_type = type_str
        if type_str in ["portal_a", "portal_b"]:
            display_type = "portal"
        elif type_str == "render_frame":
            display_type = "render frame"
            
        type_surf = header_font.render(display_type.upper(), True, UITheme.TEXT_LIGHT)
        surface.blit(type_surf, (sidebar_rect.x + 20, sidebar_rect.y + 60))
        
        y_offset = 120
        active_sliders = []
        
        if type_str == "wall":
            active_sliders = ["friction", "elasticity"]
        elif type_str == "box":
            active_sliders = ["friction", "elasticity", "box_angle", "box_width", "box_height"]
            if obj.is_dynamic:
                active_sliders.append("mass")
        elif type_str == "booster":
            active_sliders = ["booster_force"]
        elif type_str == "conveyor":
            active_sliders = ["conveyor_speed"]
        elif type_str == "escalator":
            active_sliders = ["conveyor_speed", "escalator_step"]
        elif type_str == "elevator":
            active_sliders = ["elevator_speed", "elevator_travel"]
        elif type_str == "seesaw":
            active_sliders = ["seesaw_length"]
        elif type_str == "spinner":
            active_sliders = ["spinner_speed", "spinner_blades"]
        elif type_str == "spawner":
            active_sliders = ["spawner_rate", "spawner_count"]
            
        for name in active_sliders:
            slider = self.sliders[name]
            slider.rect.x = sidebar_rect.x + 20
            slider.rect.y = sidebar_rect.y + y_offset
            slider._update_handle_pos()
            slider.draw(surface, font)
            y_offset += 65

        if type_str == "render_frame":
            surface.blit(font.render("Output Format:", True, UITheme.TEXT_MUTED),
                         (sidebar_rect.x + 20, sidebar_rect.y + y_offset))
            y_offset += 28
            bx = sidebar_rect.x + 20
            by = sidebar_rect.y + y_offset
            for fmt in FORMAT_ORDER:
                rect = pygame.Rect(bx, by, 70, 30)
                active = (obj["format"] == fmt)
                pygame.draw.rect(surface, UITheme.ACCENT_CYAN if active else UITheme.BTN_NORMAL, rect, border_radius=5)
                pygame.draw.rect(surface, UITheme.BORDER, rect, width=1, border_radius=5)
                ft = font.render(fmt, True, (0, 0, 0) if active else UITheme.TEXT_LIGHT)
                surface.blit(ft, ft.get_rect(center=rect.center))
                self.format_btn_rects.append((fmt, rect))
                bx += 78
                if bx > sidebar_rect.right - 78:
                    bx = sidebar_rect.x + 20
                    by += 38
            y_offset = (by - sidebar_rect.y) + 50
            ow, oh = RENDER_FORMATS[obj["format"]]
            w, h = render_frame_size(obj)
            surface.blit(font.render(f"{ow}x{oh}px  |  {w:.1f}x{h:.1f}m", True, UITheme.TEXT_MUTED),
                         (sidebar_rect.x + 20, sidebar_rect.y + y_offset))

        del_btn_rect = pygame.Rect(sidebar_rect.x + 20, sidebar_rect.y + sidebar_rect.height - 60, sidebar_rect.width - 40, 36)
        mouse_pos = pygame.mouse.get_pos()
        hover = del_btn_rect.collidepoint(mouse_pos)
        bg = UITheme.ACCENT_MAGENTA if hover else UITheme.BTN_NORMAL
        pygame.draw.rect(surface, bg, del_btn_rect, border_radius=6)
        pygame.draw.rect(surface, UITheme.TEXT_LIGHT, del_btn_rect, width=1, border_radius=6)
        
        del_text = font.render("DELETE OBJECT", True, (255, 255, 255) if hover else UITheme.TEXT_LIGHT)
        del_rect = del_text.get_rect(center=del_btn_rect.center)
        surface.blit(del_text, del_rect)
        
        self.update_selected_properties()
        
    def handle_inspector_click(self, pos):
        """Checks if deleting or slider dragging happened on sidebar."""
        for fmt, rect in getattr(self, "format_btn_rects", []):
            if rect.collidepoint(pos):
                if self.render_frame:
                    self.render_frame["format"] = fmt
                return
        for name, slider in self.sliders.items():
            slider.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
