import pymunk
import pygame
import math
import random
from sound_manager import SoundManager

class PhysicsManager:
    # Collision Types
    COLLISION_MARBLE = 1
    COLLISION_WALL = 2
    COLLISION_BOOSTER = 3
    COLLISION_PORTAL = 4
    COLLISION_FINISH = 5
    COLLISION_BOX = 6
    COLLISION_SEESAW = 7
    COLLISION_ESCALATOR = 8

    def __init__(self):
        self.space = pymunk.Space()
        self.space.gravity = (0.0, -30.0) # World gravity, standard in Pymunk units

        # Track collections of entities for drawing and custom logic
        self.marbles = []       # List of Pymunk shapes (circles) that are dynamic marbles
        self.walls = []         # List of Pymunk segment shapes (static)
        self.boxes = []         # List of Pymunk poly shapes (static/dynamic)
        self.boosters = []       # List of custom booster dictionary objects + sensors
        self.portals = []        # List of custom portal dictionary objects + sensors
        self.finish_lines = []   # List of static segments that act as finish lines
        self.spawners = []       # List of spawner dictionaries
        self.conveyors = []      # List of conveyor dictionary objects
        self.elevators = []      # List of elevator dictionary objects
        self.seesaws = []        # List of seesaw dictionary objects
        self.spinners = []       # List of spinner dictionary objects
        self.escalators = []     # List of escalator dictionary objects

        self._uid_counter = 0

        # Setup collision handlers
        self._setup_collision_handlers()

    def _next_uid(self):
        self._uid_counter += 1
        return self._uid_counter

    def clear(self):
        """Clears the entire physics space and resets collections."""
        # Remove all elements from space
        for shape in list(self.space.shapes):
            self.space.remove(shape)
        for body in list(self.space.bodies):
            self.space.remove(body)
        for constraint in list(self.space.constraints):
            self.space.remove(constraint)
            
        self.marbles.clear()
        self.walls.clear()
        self.boxes.clear()
        self.boosters.clear()
        self.portals.clear()
        self.finish_lines.clear()
        self.spawners.clear()
        self.conveyors.clear()
        self.elevators.clear()
        self.seesaws.clear()
        self.spinners.clear()
        self.escalators.clear()

    def step(self, dt):
        """Advances physics by dt seconds."""
        # Apply booster forces
        for booster in self.boosters:
            for marble in list(booster['active_marbles']):
                # Apply force in the booster's direction (since gravity is -30, we use force scale of ~150)
                force_vector = (booster['direction'][0] * booster['force_strength'] * 1.5, 
                                booster['direction'][1] * booster['force_strength'] * 1.5)
                # Apply impulse or force
                marble.body.apply_force_at_local_point(force_vector, (0, 0))
                
        # Update elevators
        self.update_elevators(dt)
        
        # Update seesaw cooldowns
        for ss in self.seesaws:
            if ss.get('cooldown', 0.0) > 0.0:
                ss['cooldown'] -= dt
                
        # Update escalators
        for esc in self.escalators:
            esc['offset'] = esc.get('offset', 0.0) + esc['speed'] * dt
            self.update_escalator_positions_for(esc)
                
        self.space.step(dt)
        self._handle_portal_teleportation()

    def update_elevators(self, dt):
        """Oscillates kinematic elevators up and down."""
        for elev in self.elevators:
            body = elev['body']
            pos = body.position
            # Move
            new_y = pos.y + elev['speed'] * elev['direction'] * dt
            if new_y > elev['end_y']:
                new_y = elev['end_y']
                elev['direction'] = -1
            elif new_y < elev['start_y']:
                new_y = elev['start_y']
                elev['direction'] = 1
            
            body.position = (pos.x, new_y)
            body.velocity = (0.0, elev['speed'] * elev['direction'])

    def add_marble(self, pos, radius=0.3, mass=1.0, friction=0.2, elasticity=0.6, color=None):
        """Creates a dynamic circle shape (marble)."""
        inertia = pymunk.moment_for_circle(mass, 0, radius)
        body = pymunk.Body(mass, inertia)
        body.position = pos
        shape = pymunk.Circle(body, radius)
        shape.friction = friction
        shape.elasticity = elasticity
        shape.collision_type = self.COLLISION_MARBLE
        shape.uid = self._next_uid()

        # Assign visual color
        if color is None:
            color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        shape.color = color

        # Store trail history
        shape.trail = []

        self.space.add(body, shape)
        self.marbles.append(shape)
        return shape

    def add_wall(self, p1, p2, thickness=0.1, friction=0.5, elasticity=0.8, color=(0, 255, 255)):
        """Creates a static line segment (wall)."""
        body = self.space.static_body
        shape = pymunk.Segment(body, p1, p2, thickness)
        shape.friction = friction
        shape.elasticity = elasticity
        shape.collision_type = self.COLLISION_WALL
        shape.color = color
        
        self.space.add(shape)
        self.walls.append(shape)
        return shape

    def add_box(self, pos, width, height, angle=0.0, is_dynamic=False, mass=5.0, friction=0.5, elasticity=0.3, color=(255, 0, 255)):
        """Creates a static or dynamic box shape."""
        if is_dynamic:
            inertia = pymunk.moment_for_box(mass, (width, height))
            body = pymunk.Body(mass, inertia)
            body.position = pos
            body.angle = angle
            self.space.add(body)
        else:
            body = self.space.static_body
            # For static bodies, shape is created relative to space coordinates if body is static_body
            # but we can set body's position or define coordinates relative to body.
            # Best practice is to create a separate static body at position and add shape relative to it.
            body = pymunk.Body(body_type=pymunk.Body.STATIC)
            body.position = pos
            body.angle = angle
            self.space.add(body)
            
        # Vertices relative to body center
        w_half = width / 2.0
        h_half = height / 2.0
        verts = [(-w_half, -h_half), (w_half, -h_half), (w_half, h_half), (-w_half, h_half)]
        
        shape = pymunk.Poly(body, verts)
        shape.friction = friction
        shape.elasticity = elasticity
        shape.color = color
        shape.width = width
        shape.height = height
        shape.is_dynamic = is_dynamic
        shape.collision_type = self.COLLISION_BOX
        shape.uid = self._next_uid()

        self.space.add(shape)
        self.boxes.append(shape)
        return shape

    def add_booster(self, p1, p2, force_strength=80.0, thickness=0.4, color=(0, 255, 100)):
        """Creates a booster line segment sensor that applies force along its normal or direction."""
        body = self.space.static_body
        shape = pymunk.Segment(body, p1, p2, thickness)
        shape.sensor = True
        shape.collision_type = self.COLLISION_BOOSTER
        shape.color = color
        
        # Calculate direction vector of booster
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length > 0:
            direction = (dx / length, dy / length)
        else:
            direction = (1.0, 0.0)
            
        booster_data = {
            'shape': shape,
            'p1': p1,
            'p2': p2,
            'direction': direction,
            'force_strength': force_strength,
            'color': color,
            'active_marbles': set() # track which marbles are inside
        }
        
        # We need a reference from shape to data for collision handler
        shape.custom_data = booster_data
        
        self.space.add(shape)
        self.boosters.append(booster_data)
        return booster_data

    def add_portal(self, pos_a, pos_b, radius=0.6, color=(255, 150, 0)):
        """Creates two portals (A and B). Entering portal A teleports to portal B and vice versa."""
        # Portal A shape
        body_a = pymunk.Body(body_type=pymunk.Body.STATIC)
        body_a.position = pos_a
        shape_a = pymunk.Circle(body_a, radius)
        shape_a.sensor = True
        shape_a.collision_type = self.COLLISION_PORTAL
        shape_a.color = color
        
        # Portal B shape
        body_b = pymunk.Body(body_type=pymunk.Body.STATIC)
        body_b.position = pos_b
        shape_b = pymunk.Circle(body_b, radius)
        shape_b.sensor = True
        shape_b.collision_type = self.COLLISION_PORTAL
        shape_b.color = color
        
        portal_data = {
            'shape_a': shape_a,
            'shape_b': shape_b,
            'pos_a': pos_a,
            'pos_b': pos_b,
            'radius': radius,
            'color': color,
            'teleport_cooldowns': {} # marble_shape -> timestamp/step cooldown to prevent infinite loop
        }
        
        shape_a.custom_data = (portal_data, 'a')
        shape_b.custom_data = (portal_data, 'b')
        
        self.space.add(body_a, shape_a, body_b, shape_b)
        self.portals.append(portal_data)
        return portal_data

    def add_finish_line(self, p1, p2, thickness=0.15, color=(255, 255, 255)):
        """Creates a finish line segment sensor."""
        body = self.space.static_body
        shape = pymunk.Segment(body, p1, p2, thickness)
        shape.sensor = True
        shape.collision_type = self.COLLISION_FINISH
        shape.color = color
        
        finish_data = {
            'shape': shape,
            'p1': p1,
            'p2': p2,
            'color': color,
            'crossed_marbles': [] # list of marbles that crossed, in order of arrival
        }
        shape.custom_data = finish_data
        
        self.space.add(shape)
        self.finish_lines.append(finish_data)
        return finish_data

    def _setup_collision_handlers(self):
        # 1. Booster Collision Handler
        def booster_begin(arbiter, space, data):
            marble_shape, booster_shape = arbiter.shapes
            booster_data = booster_shape.custom_data
            booster_data['active_marbles'].add(marble_shape)
            
        def booster_separate(arbiter, space, data):
            marble_shape, booster_shape = arbiter.shapes
            booster_data = booster_shape.custom_data
            if marble_shape in booster_data['active_marbles']:
                booster_data['active_marbles'].remove(marble_shape)
            
        self.space.on_collision(
            collision_type_a=self.COLLISION_MARBLE,
            collision_type_b=self.COLLISION_BOOSTER,
            begin=booster_begin,
            separate=booster_separate
        )

        # 2. Portal Collision Handler
        def portal_begin(arbiter, space, data):
            marble_shape, portal_shape = arbiter.shapes
            portal_data, portal_type = portal_shape.custom_data
            
            # Check cooldown
            if marble_shape in portal_data['teleport_cooldowns']:
                arbiter.process_collision = False
                return
                
            # Queue teleportation (we can't change positions inside the Pymunk step callback safely,
            # so we flag it and handle it right after step())
            portal_data['teleport_target'] = (marble_shape, portal_type)
            pos = marble_shape.body.position
            vel = marble_shape.body.velocity
            SoundManager.get_instance().play("portal", 0.55, pos, vel)
            
        self.space.on_collision(
            collision_type_a=self.COLLISION_MARBLE,
            collision_type_b=self.COLLISION_PORTAL,
            begin=portal_begin
        )

        # 3. Finish Line Handler
        def finish_begin(arbiter, space, data):
            marble_shape, finish_shape = arbiter.shapes
            finish_data = finish_shape.custom_data
            if marble_shape not in finish_data['crossed_marbles']:
                finish_data['crossed_marbles'].append(marble_shape)
                pos = marble_shape.body.position
                vel = marble_shape.body.velocity
                SoundManager.get_instance().play("finish", 0.65, pos, vel)
            
        self.space.on_collision(
            collision_type_a=self.COLLISION_MARBLE,
            collision_type_b=self.COLLISION_FINISH,
            begin=finish_begin
        )

        # 4. Marble - Marble Post Solve (Sound effect)
        def marble_marble_post_solve(arbiter, space, data):
            impulse = arbiter.total_impulse.length
            pos = arbiter.contact_point_set.points[0].point_a if arbiter.contact_point_set.points else arbiter.shapes[0].body.position
            vel = arbiter.shapes[0].body.velocity
            SoundManager.get_instance().play_impact("marble_marble", impulse, pos, vel)

        self.space.on_collision(
            collision_type_a=self.COLLISION_MARBLE,
            collision_type_b=self.COLLISION_MARBLE,
            post_solve=marble_marble_post_solve
        )

        # 5. Marble - Wall Post Solve (Sound effect)
        def marble_wall_post_solve(arbiter, space, data):
            impulse = arbiter.total_impulse.length
            pos = arbiter.contact_point_set.points[0].point_a if arbiter.contact_point_set.points else arbiter.shapes[0].body.position
            vel = arbiter.shapes[0].body.velocity
            SoundManager.get_instance().play_impact("marble_wall", impulse, pos, vel)

        self.space.on_collision(
            collision_type_a=self.COLLISION_MARBLE,
            collision_type_b=self.COLLISION_WALL,
            post_solve=marble_wall_post_solve
        )

        # 6. Marble - Box Post Solve (Sound effect)
        def marble_box_post_solve(arbiter, space, data):
            impulse = arbiter.total_impulse.length
            pos = arbiter.contact_point_set.points[0].point_a if arbiter.contact_point_set.points else arbiter.shapes[0].body.position
            vel = arbiter.shapes[0].body.velocity
            SoundManager.get_instance().play_impact("marble_box", impulse, pos, vel)

        self.space.on_collision(
            collision_type_a=self.COLLISION_MARBLE,
            collision_type_b=self.COLLISION_BOX,
            post_solve=marble_box_post_solve
        )

        # 7. Marble - Seesaw Collision Handler (Toggle tilt direction)
        def seesaw_begin(arbiter, space, data):
            marble_shape, seesaw_shape = arbiter.shapes
            seesaw_data = seesaw_shape.custom_data
            pos = marble_shape.body.position
            vel = marble_shape.body.velocity
            
            if seesaw_data.get('cooldown', 0.0) <= 0.0:
                # Toggle direction
                seesaw_data['target_direction'] *= -1
                if seesaw_data.get('motor') and seesaw_data['motor'] in space.constraints:
                    seesaw_data['motor'].rate = seesaw_data['target_direction'] * 2.5
                seesaw_data['cooldown'] = 0.4
                SoundManager.get_instance().play("booster", 0.5, pos, vel)
            return True

        # 8. Marble - Seesaw Post Solve (Sound effect)
        def marble_seesaw_post_solve(arbiter, space, data):
            impulse = arbiter.total_impulse.length
            pos = arbiter.contact_point_set.points[0].point_a if arbiter.contact_point_set.points else arbiter.shapes[0].body.position
            vel = arbiter.shapes[0].body.velocity
            SoundManager.get_instance().play_impact("marble_box", impulse, pos, vel)

        self.space.on_collision(
            collision_type_a=self.COLLISION_MARBLE,
            collision_type_b=self.COLLISION_SEESAW,
            begin=seesaw_begin,
            post_solve=marble_seesaw_post_solve
        )

        # 9. Marble - Escalator Collision Handler (Active marbles set tracking)
        def escalator_begin(arbiter, space, data):
            marble_shape, escalator_shape = arbiter.shapes
            escalator_data = escalator_shape.custom_data
            escalator_data['active_marbles'].add(marble_shape)
            return True
            
        def escalator_separate(arbiter, space, data):
            marble_shape, escalator_shape = arbiter.shapes
            escalator_data = escalator_shape.custom_data
            if marble_shape in escalator_data['active_marbles']:
                escalator_data['active_marbles'].remove(marble_shape)
                
        self.space.on_collision(
            collision_type_a=self.COLLISION_MARBLE,
            collision_type_b=self.COLLISION_ESCALATOR,
            begin=escalator_begin,
            separate=escalator_separate
        )

    def _handle_portal_teleportation(self):
        # Apply queued teleports and handle cooldown tick down
        for portal in self.portals:
            # Cool down existing entries
            expired = []
            for m_shape, cd in portal['teleport_cooldowns'].items():
                portal['teleport_cooldowns'][m_shape] = cd - 1
                if portal['teleport_cooldowns'][m_shape] <= 0:
                    expired.append(m_shape)
            for m_shape in expired:
                del portal['teleport_cooldowns'][m_shape]
                
            # Perform queued teleportation
            if 'teleport_target' in portal:
                marble_shape, portal_source = portal['teleport_target']
                del portal['teleport_target'] # Clear target
                
                # Check cooldown again
                if marble_shape in portal['teleport_cooldowns']:
                    continue
                    
                # Calculate new position
                if portal_source == 'a':
                    dest_pos = portal['pos_b']
                else:
                    dest_pos = portal['pos_a']
                    
                # Teleport body
                # Add a tiny offset so the marble doesn't immediately re-collide in the opposite portal center
                marble_shape.body.position = dest_pos
                # Keep velocity, maybe add a small kick forward
                
                # Set cooldown (number of physics steps)
                portal['teleport_cooldowns'][marble_shape] = 60 # 1 second if step is 1/60s

    def add_spawner(self, pos, rate=0.2, count=20, marble_color=None):
        """Creates a marble spawner that periodically releases marbles during simulation."""
        spawner = {
            'pos': pos,
            'rate': rate,              # spawn rate in seconds
            'count': count,            # total count to spawn
            'spawned': 0,              # spawned count
            'last_spawn_time': -rate,  # start ready to spawn immediately
            'marble_color': marble_color,
            'color': (255, 230, 0)
        }
        self.spawners.append(spawner)
        return spawner

    def update_spawners(self, sim_time):
        """Checks and spawns marbles from active spawners."""
        for spawner in self.spawners:
            if spawner['spawned'] < spawner['count']:
                if sim_time - spawner['last_spawn_time'] >= spawner['rate']:
                    # Spawn marble with a tiny random horizontal offset
                    rx = random.uniform(-0.05, 0.05)
                    ry = random.uniform(-0.05, 0.05)
                    spawn_pos = (spawner['pos'][0] + rx, spawner['pos'][1] + ry)
                    self.add_marble(spawn_pos, radius=0.3, color=spawner['marble_color'])
                    spawner['spawned'] += 1
                    spawner['last_spawn_time'] = sim_time

    def resize_box(self, box_shape, new_width, new_height):
        """Recreates a box shape inside space with new dimensions, maintaining body and materials."""
        body = box_shape.body
        friction = box_shape.friction
        elasticity = box_shape.elasticity
        color = box_shape.color
        is_dynamic = box_shape.is_dynamic
        
        self.space.remove(box_shape)
        
        w_half = new_width / 2.0
        h_half = new_height / 2.0
        verts = [(-w_half, -h_half), (w_half, -h_half), (w_half, h_half), (-w_half, h_half)]
        
        new_shape = pymunk.Poly(body, verts)
        new_shape.friction = friction
        new_shape.elasticity = elasticity
        new_shape.color = color
        new_shape.width = new_width
        new_shape.height = new_height
        new_shape.is_dynamic = is_dynamic
        
        idx = self.boxes.index(box_shape)
        self.boxes[idx] = new_shape
        self.space.add(new_shape)
        return new_shape

    def add_conveyor(self, p1, p2, speed=6.0, thickness=0.1, color=(0, 180, 255)):
        """Creates a conveyor segment that pushes marbles along its length."""
        body = self.space.static_body
        shape = pymunk.Segment(body, p1, p2, thickness)
        shape.friction = 0.9  # High friction helps apply surface velocity
        shape.elasticity = 0.1
        shape.collision_type = self.COLLISION_WALL
        shape.color = color
        
        # Pymunk surface velocity is tangent-aligned for segments
        shape.surface_velocity = (speed, 0.0)
        
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        direction = (dx / length, dy / length) if length > 0 else (1.0, 0.0)
        
        conveyor_data = {
            'shape': shape,
            'p1': p1,
            'p2': p2,
            'speed': speed,
            'color': color,
            'direction': direction
        }
        shape.custom_data = conveyor_data
        
        self.space.add(shape)
        self.conveyors.append(conveyor_data)
        return conveyor_data

    def add_elevator(self, pos, width=2.5, height=0.4, travel_distance=8.0, speed=3.0, color=(255, 165, 0)):
        """Creates a vertical lifting platform."""
        body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        body.position = pos
        
        w_half = width / 2.0
        h_half = height / 2.0
        verts = [(-w_half, -h_half), (w_half, -h_half), (w_half, h_half), (-w_half, h_half)]
        
        shape = pymunk.Poly(body, verts)
        shape.friction = 0.7
        shape.elasticity = 0.1
        shape.color = color
        shape.collision_type = self.COLLISION_WALL

        elev_data = {
            'body': body,
            'shape': shape,
            'pos': pos,
            'width': width,
            'height': height,
            'start_y': pos[1],
            'end_y': pos[1] + travel_distance,
            'speed': speed,
            'direction': 1,
            'color': color,
            'uid': self._next_uid()
        }
        shape.custom_data = elev_data
        
        self.space.add(body, shape)
        self.elevators.append(elev_data)
        return elev_data

    def add_seesaw(self, pos, length=6.0, thickness=0.3, color=(255, 230, 0)):
        """Creates a dynamic pivot seesaw bar."""
        pivot_body = pymunk.Body(body_type=pymunk.Body.STATIC)
        pivot_body.position = pos
        
        mass = 2.0
        moment = pymunk.moment_for_box(mass, (length, thickness))
        body = pymunk.Body(mass, moment)
        body.position = pos
        
        w_half = length / 2.0
        h_half = thickness / 2.0
        verts = [(-w_half, -h_half), (w_half, -h_half), (w_half, h_half), (-w_half, h_half)]
        
        shape = pymunk.Poly(body, verts)
        shape.friction = 0.5
        shape.elasticity = 0.2
        shape.color = color
        shape.collision_type = self.COLLISION_SEESAW

        joint = pymunk.PivotJoint(pivot_body, body, pos)
        limit = pymunk.RotaryLimitJoint(pivot_body, body, -math.radians(30), math.radians(30))

        # Simple motor with moderate torque to drive tilt
        motor = pymunk.SimpleMotor(pivot_body, body, -2.5) # Start by tilting clockwise
        motor.max_force = 150.0

        seesaw_data = {
            'pivot_body': pivot_body,
            'body': body,
            'shape': shape,
            'pos': pos,
            'length': length,
            'thickness': thickness,
            'color': color,
            'joint': joint,
            'limit': limit,
            'motor': motor,
            'target_direction': -1,
            'cooldown': 0.0,
            'uid': self._next_uid()
        }
        shape.custom_data = seesaw_data
        
        self.space.add(body, shape, joint, limit, motor)
        self.seesaws.append(seesaw_data)
        return seesaw_data

    def add_spinner(self, pos, radius=2.5, num_blades=4, is_motorized=True, motor_speed=2.0, color=(0, 255, 255)):
        """Creates a motorized or passive spinner with multiple blades."""
        pivot_body = pymunk.Body(body_type=pymunk.Body.STATIC)
        pivot_body.position = pos
        
        mass = 3.0
        moment = pymunk.moment_for_circle(mass, 0, radius)
        body = pymunk.Body(mass, moment)
        body.position = pos
        
        shapes = []
        blade_thickness = 0.3
        
        for i in range(num_blades):
            angle = i * (2 * math.pi / num_blades)
            w = radius
            h = blade_thickness
            c, s = math.cos(angle), math.sin(angle)
            x_offset = w / 2.0
            
            verts = [
                (x_offset - w/2.0, -h/2.0),
                (x_offset + w/2.0, -h/2.0),
                (x_offset + w/2.0, h/2.0),
                (x_offset - w/2.0, h/2.0)
            ]
            
            rotated_verts = []
            for vx, vy in verts:
                rx = vx * c - vy * s
                ry = vx * s + vy * c
                rotated_verts.append((rx, ry))
                
            shape = pymunk.Poly(body, rotated_verts)
            shape.friction = 0.5
            shape.elasticity = 0.3
            shape.color = color
            shape.collision_type = self.COLLISION_BOX
            shapes.append(shape)
            
        joint = pymunk.PivotJoint(pivot_body, body, pos)

        motor = None
        if is_motorized:
            motor = pymunk.SimpleMotor(pivot_body, body, motor_speed)

        spinner_data = {
            'pivot_body': pivot_body,
            'body': body,
            'shapes': shapes,
            'pos': pos,
            'radius': radius,
            'num_blades': num_blades,
            'is_motorized': is_motorized,
            'motor_speed': motor_speed,
            'color': color,
            'joint': joint,
            'motor': motor,
            'uid': self._next_uid()
        }

        for s in shapes:
            s.custom_data = spinner_data
            
        self.space.add(body, joint)
        for s in shapes:
            self.space.add(s)
        if motor:
            self.space.add(motor)
            
        self.spinners.append(spinner_data)
        return spinner_data

    def add_escalator(self, p1, p2, speed=4.0, thickness=0.15, step_size=0.8, color=(255, 100, 0)):
        """Creates an escalator segment that carries marbles up diagonal steps."""
        body = self.space.static_body
        shape = pymunk.Segment(body, p1, p2, thickness)
        shape.sensor = True  # Make it a sensor so marbles only collide with physical steps
        shape.collision_type = self.COLLISION_ESCALATOR
        shape.color = color
        
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        direction = (dx / length, dy / length) if length > 0 else (1.0, 0.0)
        
        escalator_data = {
            'shape': shape,
            'p1': p1,
            'p2': p2,
            'speed': speed,
            'step_size': step_size,
            'color': color,
            'direction': direction,
            'active_marbles': set(),
            'steps': [],
            'offset': 0.0
        }
        shape.custom_data = escalator_data
        
        self.space.add(shape)
        self.escalators.append(escalator_data)
        self.recreate_escalator_steps(escalator_data)
        return escalator_data

    def recreate_escalator_steps(self, esc):
        # Remove old steps from space
        if 'steps' in esc:
            for body, tread, riser in esc['steps']:
                if tread in self.space.shapes:
                    self.space.remove(tread)
                if riser in self.space.shapes:
                    self.space.remove(riser)
                if body in self.space.bodies:
                    self.space.remove(body)
        esc['steps'] = []
        
        # Calculate new step parameters
        p1 = esc['p1']
        p2 = esc['p2']
        step_size = max(0.1, esc.get('step_size', 0.8))
        
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length <= 0:
            return
            
        ux = dx / length
        uy = dy / length
        esc['direction'] = (ux, uy)
        
        num_steps = int(math.ceil(length / step_size)) + 2
        
        dx_step = step_size * ux
        dy_step = step_size * uy
        
        for i in range(num_steps):
            # Create a kinematic body
            body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
            
            # Local coordinates of tread: from -dx_step/2 to dx_step/2 at y=0.
            tread = pymunk.Segment(body, (-dx_step/2.0, 0.0), (dx_step/2.0, 0.0), 0.05)
            tread.friction = 1.8
            tread.elasticity = 0.05
            tread.collision_type = self.COLLISION_WALL
            tread.color = esc['color']
            
            # Local coordinates of riser: from dx_step/2 at y=0 to dx_step/2 at y=dy_step.
            riser = pymunk.Segment(body, (dx_step/2.0, 0.0), (dx_step/2.0, dy_step), 0.05)
            riser.friction = 1.8
            riser.elasticity = 0.05
            riser.collision_type = self.COLLISION_WALL
            riser.color = esc['color']
            
            self.space.add(body, tread, riser)
            esc['steps'].append((body, tread, riser))
            
        # Update positions once initially based on current offset
        self.update_escalator_positions_for(esc)

    def update_escalator_positions_for(self, esc):
        p1 = esc['p1']
        p2 = esc['p2']
        step_size = max(0.1, esc.get('step_size', 0.8))
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length <= 0 or not esc.get('steps'):
            return
            
        ux = dx / length
        uy = dy / length
        
        num_steps = len(esc['steps'])
        W = num_steps * step_size
        d_min = -step_size
        
        offset = esc.get('offset', 0.0)
        
        # Calculate velocity vector
        vx = esc['speed'] * ux
        vy = esc['speed'] * uy
        
        min_x, max_x = min(p1[0], p2[0]), max(p1[0], p2[0])
        min_y, max_y = min(p1[1], p2[1]), max(p1[1], p2[1])
        
        def clip_pt(x, y):
            return (max(min_x, min(max_x, x)), max(min_y, min(max_y, y)))
            
        dy_step = step_size * uy
        
        for i, (body, tread, riser) in enumerate(esc['steps']):
            # Current distance along the escalator for this step
            t_i = (i * step_size + offset) % W
            d_i = d_min + t_i
            
            # Position of the body in world space
            # Center of the tread is at d_i + step_size/2
            bx = p1[0] + ux * (d_i + step_size / 2.0)
            by = p1[1] + uy * (d_i + step_size / 2.0)
            
            body.position = (bx, by)
            body.velocity = (vx, vy)
            
            # Unclipped world coordinates of tread endpoints
            ta_wx = p1[0] + ux * d_i
            ta_wy = by
            tb_wx = p1[0] + ux * (d_i + step_size)
            tb_wy = by
            
            # Unclipped world coordinates of riser endpoints
            ra_wx = tb_wx
            ra_wy = tb_wy
            rb_wx = tb_wx
            rb_wy = tb_wy + dy_step
            
            # Clip world coordinates to escalator bounding box
            ta_cx, ta_cy = clip_pt(ta_wx, ta_wy)
            tb_cx, tb_cy = clip_pt(tb_wx, tb_wy)
            ra_cx, ra_cy = clip_pt(ra_wx, ra_wy)
            rb_cx, rb_cy = clip_pt(rb_wx, rb_wy)
            
            # Convert clipped world coordinates to body local coordinates
            ta_loc = body.world_to_local((ta_cx, ta_cy))
            tb_loc = body.world_to_local((tb_cx, tb_cy))
            ra_loc = body.world_to_local((ra_cx, ra_cy))
            rb_loc = body.world_to_local((rb_cx, rb_cy))
            
            # Set endpoints of the segment shapes
            tread.unsafe_set_endpoints(ta_loc, tb_loc)
            riser.unsafe_set_endpoints(ra_loc, rb_loc)
            
            self.space.reindex_shape(tread)
            self.space.reindex_shape(riser)
            
            # Toggle sensor if the step is outside [0, length]
            # The step spans from d_i to d_i + step_size
            is_outside = (d_i + step_size < -0.05) or (d_i > length + 0.05)
            tread.sensor = is_outside
            riser.sensor = is_outside
