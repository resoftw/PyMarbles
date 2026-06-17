import json
import random
import math
import os

class MapManager:
    @staticmethod
    def save_map(physics_manager, filepath, camera=None):
        """Saves the current physics layout to a JSON file."""
        data = {
            "gravity": list(physics_manager.space.gravity),
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
        
        # Save walls
        for wall in physics_manager.walls:
            # Check if wall is a conveyor or escalator (it might be in walls list physically, but let's check custom_data)
            if hasattr(wall, 'custom_data') and (wall.custom_data in physics_manager.conveyors or wall.custom_data in physics_manager.escalators):
                continue # saved separately
            data["walls"].append({
                "p1": [wall.a[0], wall.a[1]],
                "p2": [wall.b[0], wall.b[1]],
                "thickness": wall.radius,
                "friction": wall.friction,
                "elasticity": wall.elasticity,
                "color": list(wall.color) if hasattr(wall, 'color') else [0, 255, 255]
            })
            
        # Save boxes (polys)
        for box in physics_manager.boxes:
            # Skip spinner blades or seesaw shapes as they are saved in their collections
            if hasattr(box, 'custom_data') and (box.custom_data in physics_manager.seesaws or box.custom_data in physics_manager.spinners):
                continue
            data["boxes"].append({
                "pos": [box.body.position[0], box.body.position[1]],
                "width": box.width,
                "height": box.height,
                "angle": box.body.angle,
                "is_dynamic": box.is_dynamic,
                "mass": box.body.mass if box.is_dynamic else 0.0,
                "friction": box.friction,
                "elasticity": box.elasticity,
                "color": list(box.color) if hasattr(box, 'color') else [255, 0, 255]
            })
            
        # Save boosters
        for booster in physics_manager.boosters:
            data["boosters"].append({
                "p1": [booster["p1"][0], booster["p1"][1]],
                "p2": [booster["p2"][0], booster["p2"][1]],
                "force_strength": booster["force_strength"],
                "color": list(booster["color"])
            })
            
        # Save portals
        for portal in physics_manager.portals:
            data["portals"].append({
                "pos_a": [portal["pos_a"][0], portal["pos_a"][1]],
                "pos_b": [portal["pos_b"][0], portal["pos_b"][1]],
                "radius": portal["radius"],
                "color": list(portal["color"])
            })
            
        # Save finish lines
        for finish in physics_manager.finish_lines:
            data["finish_lines"].append({
                "p1": [finish["p1"][0], finish["p1"][1]],
                "p2": [finish["p2"][0], finish["p2"][1]],
                "color": list(finish["color"])
            })
            
        # Save spawners
        for spawner in physics_manager.spawners:
            data["spawners"].append({
                "pos": [spawner["pos"][0], spawner["pos"][1]],
                "rate": spawner["rate"],
                "count": spawner["count"],
                "marble_color": list(spawner["marble_color"]) if spawner["marble_color"] else None
            })
            
        # Save conveyors
        for conv in physics_manager.conveyors:
            data["conveyors"].append({
                "p1": [conv["p1"][0], conv["p1"][1]],
                "p2": [conv["p2"][0], conv["p2"][1]],
                "speed": conv["speed"],
                "color": list(conv["color"])
            })
            
        # Save escalators
        for esc in physics_manager.escalators:
            data["escalators"].append({
                "p1": [esc["p1"][0], esc["p1"][1]],
                "p2": [esc["p2"][0], esc["p2"][1]],
                "speed": esc["speed"],
                "step_size": esc.get("step_size", 0.8),
                "color": list(esc["color"])
            })
            
        # Save elevators
        for elev in physics_manager.elevators:
            data["elevators"].append({
                "pos": [elev["pos"][0], elev["pos"][1]],
                "width": elev["width"],
                "height": elev["height"],
                "travel_distance": elev["end_y"] - elev["start_y"],
                "speed": elev["speed"],
                "color": list(elev["color"])
            })
            
        # Save seesaws
        for ss in physics_manager.seesaws:
            data["seesaws"].append({
                "pos": [ss["pos"][0], ss["pos"][1]],
                "length": ss["length"],
                "thickness": ss["thickness"],
                "color": list(ss["color"])
            })
            
        # Save spinners
        for sp in physics_manager.spinners:
            data["spinners"].append({
                "pos": [sp["pos"][0], sp["pos"][1]],
                "radius": sp["radius"],
                "num_blades": sp["num_blades"],
                "is_motorized": sp["is_motorized"],
                "motor_speed": sp["motor_speed"],
                "color": list(sp["color"])
            })
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        if camera is not None:
            data["camera"] = camera

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def load_map(physics_manager, filepath):
        """Loads a layout from a JSON file into the physics manager."""
        if not os.path.exists(filepath):
            return False
            
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading map JSON: {e}")
            return False
            
        physics_manager.clear()
        
        if "gravity" in data:
            physics_manager.space.gravity = tuple(data["gravity"])
            
        # Load walls
        for wall_data in data.get("walls", []):
            physics_manager.add_wall(
                p1=tuple(wall_data["p1"]),
                p2=tuple(wall_data["p2"]),
                thickness=wall_data.get("thickness", 0.1),
                friction=wall_data.get("friction", 0.5),
                elasticity=wall_data.get("elasticity", 0.8),
                color=tuple(wall_data.get("color", (0, 255, 255)))
            )
            
        # Load boxes
        for box_data in data.get("boxes", []):
            physics_manager.add_box(
                pos=tuple(box_data["pos"]),
                width=box_data["width"],
                height=box_data["height"],
                angle=box_data.get("angle", 0.0),
                is_dynamic=box_data.get("is_dynamic", False),
                mass=box_data.get("mass", 5.0),
                friction=box_data.get("friction", 0.5),
                elasticity=box_data.get("elasticity", 0.3),
                color=tuple(box_data.get("color", (255, 0, 255)))
            )
            
        # Load boosters
        for booster_data in data.get("boosters", []):
            physics_manager.add_booster(
                p1=tuple(booster_data["p1"]),
                p2=tuple(booster_data["p2"]),
                force_strength=booster_data.get("force_strength", 80.0),
                color=tuple(booster_data.get("color", (0, 255, 100)))
            )
            
        # Load portals
        for portal_data in data.get("portals", []):
            physics_manager.add_portal(
                pos_a=tuple(portal_data["pos_a"]),
                pos_b=tuple(portal_data["pos_b"]),
                radius=portal_data.get("radius", 0.6),
                color=tuple(portal_data.get("color", (255, 150, 0)))
            )
            
        # Load finish lines
        for finish_data in data.get("finish_lines", []):
            physics_manager.add_finish_line(
                p1=tuple(finish_data["p1"]),
                p2=tuple(finish_data["p2"]),
                color=tuple(finish_data.get("color", (255, 255, 255)))
            )
            
        # Load spawners
        for spawner_data in data.get("spawners", []):
            physics_manager.add_spawner(
                pos=tuple(spawner_data["pos"]),
                rate=spawner_data.get("rate", 0.2),
                count=spawner_data.get("count", 20),
                marble_color=tuple(spawner_data["marble_color"]) if spawner_data.get("marble_color") else None
            )
            
        # Load conveyors
        for conv_data in data.get("conveyors", []):
            physics_manager.add_conveyor(
                p1=tuple(conv_data["p1"]),
                p2=tuple(conv_data["p2"]),
                speed=conv_data.get("speed", 6.0),
                color=tuple(conv_data.get("color", (0, 180, 255)))
            )
            
        # Load escalators
        for esc_data in data.get("escalators", []):
            physics_manager.add_escalator(
                p1=tuple(esc_data["p1"]),
                p2=tuple(esc_data["p2"]),
                speed=esc_data.get("speed", 4.0),
                step_size=esc_data.get("step_size", 0.8),
                color=tuple(esc_data.get("color", (255, 100, 0)))
            )
            
        # Load elevators
        for elev_data in data.get("elevators", []):
            physics_manager.add_elevator(
                pos=tuple(elev_data["pos"]),
                width=elev_data.get("width", 2.5),
                height=elev_data.get("height", 0.4),
                travel_distance=elev_data.get("travel_distance", 8.0),
                speed=elev_data.get("speed", 3.0),
                color=tuple(elev_data.get("color", (255, 165, 0)))
            )
            
        # Load seesaws
        for ss_data in data.get("seesaws", []):
            physics_manager.add_seesaw(
                pos=tuple(ss_data["pos"]),
                length=ss_data.get("length", 6.0),
                thickness=ss_data.get("thickness", 0.3),
                color=tuple(ss_data.get("color", (255, 230, 0)))
            )
            
        # Load spinners
        for sp_data in data.get("spinners", []):
            physics_manager.add_spinner(
                pos=tuple(sp_data["pos"]),
                radius=sp_data.get("radius", 2.5),
                num_blades=sp_data.get("num_blades", 4),
                is_motorized=sp_data.get("is_motorized", True),
                motor_speed=sp_data.get("motor_speed", 2.0),
                color=tuple(sp_data.get("color", (0, 255, 255)))
            )

        return data.get("camera")

    @staticmethod
    def load_preset(physics_manager, name):
        """Loads a built-in level preset."""
        physics_manager.clear()
        physics_manager.space.gravity = (0.0, -30.0)
        
        if name == "Plinko Race":
            # 1. Spawner at top
            physics_manager.add_spawner(pos=(0.0, 16.0), rate=0.15, count=25)
            
            # Starting funnel
            physics_manager.add_wall(p1=(-4.0, 15.0), p2=(-1.0, 12.0), friction=0.1, color=(100, 100, 255))
            physics_manager.add_wall(p1=(4.0, 15.0), p2=(1.0, 12.0), friction=0.1, color=(100, 100, 255))
            physics_manager.add_wall(p1=(-1.0, 12.0), p2=(-1.0, 10.0), friction=0.1, color=(100, 100, 255))
            physics_manager.add_wall(p1=(1.0, 12.0), p2=(1.0, 10.0), friction=0.1, color=(100, 100, 255))
            
            # Plinko peg board
            rows = 7
            for r in range(rows):
                y = 8.0 - r * 2.0
                pegs_count = r + 2
                start_x = -pegs_count / 2.0 + 0.5
                for c in range(pegs_count):
                    x = (start_x + c) * 2.0
                    # Add circular static boxes to act as pegs
                    physics_manager.add_box(pos=(x, y), width=0.4, height=0.4, is_dynamic=False, friction=0.1, elasticity=0.8, color=(255, 100, 100))
                    
            # Outbound boundaries
            physics_manager.add_wall(p1=(-8.0, 10.0), p2=(-8.0, -6.0), friction=0.1, color=(100, 100, 255))
            physics_manager.add_wall(p1=(8.0, 10.0), p2=(8.0, -6.0), friction=0.1, color=(100, 100, 255))
            
            # Funnel at the bottom of Plinko pegs
            physics_manager.add_wall(p1=(-8.0, -6.0), p2=(-2.0, -10.0), friction=0.1, color=(100, 100, 255))
            physics_manager.add_wall(p1=(8.0, -6.0), p2=(2.0, -10.0), friction=0.1, color=(100, 100, 255))
            
            # Speed slide track down from funnel
            physics_manager.add_wall(p1=(-2.0, -10.0), p2=(-2.0, -12.0), friction=0.1, color=(100, 100, 255))
            physics_manager.add_wall(p1=(2.0, -10.0), p2=(2.0, -12.0), friction=0.1, color=(100, 100, 255))
            
            # Slope and booster
            physics_manager.add_wall(p1=(-2.0, -12.0), p2=(5.0, -18.0), friction=0.01, elasticity=0.2, color=(0, 255, 255))
            physics_manager.add_wall(p1=(2.0, -12.0), p2=(7.0, -16.0), friction=0.01, elasticity=0.2, color=(0, 255, 255))
            
            # Booster pad on slope
            physics_manager.add_booster(p1=(0.0, -13.7), p2=(4.0, -17.1), force_strength=120.0, color=(0, 255, 100))
            
            # A jump at the end
            physics_manager.add_wall(p1=(5.0, -18.0), p2=(9.0, -17.0), friction=0.01, elasticity=0.2, color=(255, 0, 255)) # Ramp up
            physics_manager.add_wall(p1=(7.0, -16.0), p2=(9.5, -15.0), friction=0.01, color=(255, 0, 255)) # Ramp ceiling
            
            # Catch basin at the far bottom-left
            physics_manager.add_wall(p1=(-12.0, -20.0), p2=(-3.0, -22.0), friction=0.1, color=(100, 100, 255)) # Floor
            physics_manager.add_wall(p1=(-12.0, -16.0), p2=(-12.0, -20.0), friction=0.1, color=(100, 100, 255)) # Left wall
            physics_manager.add_wall(p1=(-3.0, -22.0), p2=(-3.0, -18.0), friction=0.1, color=(100, 100, 255)) # Right wall of catch basin
            
            # Finish line in catch basin
            physics_manager.add_finish_line(p1=(-11.5, -19.5), p2=(-3.5, -21.3))
            
        elif name == "Loop-the-Loop & Jump":
            # High speed track
            # Spawner
            physics_manager.add_spawner(pos=(-12.0, 18.0), rate=0.2, count=20)
            
            # High drop ramp
            physics_manager.add_wall(p1=(-14.0, 17.0), p2=(-4.0, 4.0), friction=0.01, elasticity=0.1, color=(0, 255, 255))
            physics_manager.add_wall(p1=(-11.0, 19.0), p2=(-2.5, 7.5), friction=0.01, elasticity=0.1, color=(0, 255, 255))
            
            # Booster on drop
            physics_manager.add_booster(p1=(-10.0, 11.8), p2=(-6.0, 6.6), force_strength=100.0, color=(0, 255, 100))
            
            # Loop sequence center at (2.0, 3.0), radius 3.5
            cx, cy = 2.0, 3.0
            r = 3.2
            num_points = 24
            loop_points = []
            # Generate points in a circle winding clockwise/counterclockwise
            # Entrance at (-4, 4) matches loop start angle
            for i in range(num_points + 1):
                # Angle goes from 225 degrees to 225 - 360 degrees
                angle = (225 - (i / num_points) * 360) * math.pi / 180.0
                px = cx + r * math.cos(angle)
                py = cy + r * math.sin(angle)
                loop_points.append((px, py))
                
            # Create loop outer wall segments
            for i in range(len(loop_points) - 1):
                physics_manager.add_wall(p1=loop_points[i], p2=loop_points[i+1], friction=0.01, elasticity=0.1, color=(255, 100, 255))
                
            # Exit ramp starting around loop end at (cx + r*cos(225), cy + r*sin(225))
            # which is around (-0.2, 0.7)
            physics_manager.add_wall(p1=(1.5, 0.0), p2=(7.0, -1.0), friction=0.01, elasticity=0.1, color=(0, 255, 255)) # Ramp up to jump
            physics_manager.add_wall(p1=(7.0, -1.0), p2=(10.0, 0.5), friction=0.01, elasticity=0.1, color=(0, 255, 255)) # Jump ramp lip
            
            # Landing zone further right
            physics_manager.add_wall(p1=(15.0, -4.0), p2=(25.0, -6.0), friction=0.1, color=(0, 255, 255))
            physics_manager.add_wall(p1=(15.0, -4.0), p2=(15.0, -1.0), friction=0.1, color=(100, 100, 255)) # Catch wall
            physics_manager.add_wall(p1=(25.0, -6.0), p2=(25.0, -2.0), friction=0.1, color=(100, 100, 255))
            
            # Finish line in landing zone
            physics_manager.add_finish_line(p1=(15.5, -4.1), p2=(24.5, -5.9))

        elif name == "Portal Chaos":
            # A level where marbles get teleported multiple times
            physics_manager.add_spawner(pos=(-8.0, 15.0), rate=0.15, count=25)
            
            # Top slide
            physics_manager.add_wall(p1=(-10.0, 14.0), p2=(-4.0, 11.0), friction=0.05, color=(0, 255, 255))
            # Portal 1 Entrance
            physics_manager.add_portal(pos_a=(-4.5, 10.0), pos_b=(8.0, 8.0), color=(255, 100, 0))
            
            # Slide 2 (under portal B at (8.0, 8.0))
            physics_manager.add_wall(p1=(9.0, 7.0), p2=(2.0, 4.0), friction=0.05, color=(0, 255, 255))
            # Portal 2 Entrance
            physics_manager.add_portal(pos_a=(2.5, 3.2), pos_b=(-8.0, 0.0), color=(0, 255, 100))
            
            # Slide 3 (under portal B at (-8.0, 0.0))
            physics_manager.add_wall(p1=(-9.5, -1.0), p2=(-2.0, -4.0), friction=0.05, color=(0, 255, 255))
            # Portal 3 Entrance
            physics_manager.add_portal(pos_a=(-2.5, -4.8), pos_b=(6.0, -6.0), color=(255, 0, 255))
            
            # Catch slide under portal 3 B at (6.0, -6.0)
            physics_manager.add_wall(p1=(7.5, -7.0), p2=(-6.0, -12.0), friction=0.05, color=(0, 255, 255))
            
            # Bumper pegs along catch slide
            physics_manager.add_box(pos=(3.0, -8.0), width=0.5, height=0.5, is_dynamic=False, elasticity=1.2, color=(255, 50, 50))
            physics_manager.add_box(pos=(0.0, -9.5), width=0.5, height=0.5, is_dynamic=False, elasticity=1.2, color=(255, 50, 50))
            physics_manager.add_box(pos=(-3.0, -11.0), width=0.5, height=0.5, is_dynamic=False, elasticity=1.2, color=(255, 50, 50))
            
            # Bottom drop floor
            physics_manager.add_wall(p1=(-8.0, -15.0), p2=(8.0, -17.0), friction=0.1, color=(100, 100, 255))
            physics_manager.add_wall(p1=(-8.0, -12.0), p2=(-8.0, -15.0), friction=0.1, color=(100, 100, 255))
            physics_manager.add_wall(p1=(8.0, -13.0), p2=(8.0, -17.0), friction=0.1, color=(100, 100, 255))
            
            # Finish line
            physics_manager.add_finish_line(p1=(-7.5, -15.1), p2=(7.5, -16.9))

        return True

    @staticmethod
    def generate_random_map(physics_manager, seed=None):
        """Generates a fully procedural, neat, and continuous race track."""
        import colorsys
        import pygame
        
        if seed is not None:
            random.seed(seed)
        else:
            # Seed with a random integer to allow variability
            random.seed(random.randint(0, 100000))
            
        physics_manager.clear()
        physics_manager.space.gravity = (0.0, -30.0)
        
        conveyor_lines = set()
        def get_key(p1, p2):
            p1_r = (round(p1[0], 2), round(p1[1], 2))
            p2_r = (round(p2[0], 2), round(p2[1], 2))
            return tuple(sorted([p1_r, p2_r]))
        
        # Choose size category
        size_category = random.choice(["Small", "Medium", "Large"])
        
        # Determine segments list and starting height based on size
        if size_category == "Small":
            start_y = 50.0
            segment_types = ["slope", random.choice(["conveyor_slope", "seesaw_drop"]), "slope", "arena"]
        elif size_category == "Medium":
            start_y = 90.0
            segment_types = ["slope", "plinko", "slope"]
            segment_types.append(random.choice(["seesaw_drop", "spinners"]))
            segment_types.append("slope")
            if random.random() > 0.5:
                segment_types.append("elevator_lift")
                segment_types.extend(["slope", "conveyor_slope"])
            else:
                segment_types.extend(["booster", "slope"])
            segment_types.append("arena")
        else: # Large
            start_y = 165.0
            segment_types = ["slope", "plinko", "conveyor_slope", "seesaw_drop", "portal"]
            segment_types.extend(["slope", "spinners", "elevator_lift", "slope", "portal"])
            segment_types.extend(["slope", "booster", "seesaw_drop", "arena"])
            
        # Spawn 50 marbles at the top
        start_x = 0.0
        physics_manager.add_spawner(pos=(start_x, start_y + 3.0), rate=0.15, count=50)
        
        # Lists to store child entities to build
        portals_to_create = []
        pegs_to_create = []
        arena_bumpers_to_create = []
        finish_lines_to_create = []
        
        # Paths list
        paths = []
        current_path = {
            "left": [(-5.0, start_y + 4.0), (-1.75, start_y)],
            "right": [(5.0, start_y + 4.0), (1.75, start_y)],
            "cap_start": False,
            "cap_end": False
        }
        paths.append(current_path)
        
        current_x = start_x
        current_y = start_y
        direction = random.choice([1, -1])
        
        # Estimate total height for color gradient
        min_y = start_y - len(segment_types) * 16.0
        
        def get_y_color(y_val):
            t = (start_y - y_val) / max(1.0, start_y - min_y)
            t = max(0.0, min(1.0, t))
            hue = 0.5 + 0.45 * t
            r, g, b = colorsys.hls_to_rgb(hue % 1.0, 0.55, 1.0)
            return (int(r * 255), int(g * 255), int(b * 255))
            
        for seg_type in segment_types:
            if seg_type == "slope":
                width = random.uniform(12.0, 20.0)
                drop = random.uniform(6.0, 10.0)
                
                next_x = current_x + direction * width
                next_y = current_y - drop
                
                # Slope nodes
                current_path["left"].append((next_x - 1.75, next_y))
                current_path["right"].append((next_x + 1.75, next_y))
                
                # Turn vertical landing drop (3.0 units) to redirect marbles smoothly
                turn_y = next_y - 3.0
                current_path["left"].append((next_x - 1.75, turn_y))
                current_path["right"].append((next_x + 1.75, turn_y))
                
                current_x = next_x
                current_y = turn_y
                direction = -direction
                
            elif seg_type == "booster":
                width = random.uniform(15.0, 24.0)
                drop = random.uniform(5.0, 8.0)
                
                next_x = current_x + direction * width
                next_y = current_y - drop
                
                # Add slope nodes
                current_path["left"].append((next_x - 1.75, next_y))
                current_path["right"].append((next_x + 1.75, next_y))
                
                # Add booster on the floor
                if direction == 1:
                    bp1 = (current_x - 1.4, current_y)
                    bp2 = (next_x - 1.4, next_y)
                else:
                    bp1 = (current_x + 1.4, current_y)
                    bp2 = (next_x + 1.4, next_y)
                    
                physics_manager.add_booster(p1=bp1, p2=bp2, force_strength=random.uniform(130.0, 180.0), color=(0, 255, 100))
                
                # Turn landing
                turn_y = next_y - 3.0
                current_path["left"].append((next_x - 1.75, turn_y))
                current_path["right"].append((next_x + 1.75, turn_y))
                
                current_x = next_x
                current_y = turn_y
                direction = -direction
                
            elif seg_type == "plinko":
                plinko_width = 8.0
                drop = random.uniform(10.0, 16.0)
                
                # Funnel open
                funnel_y = current_y - 3.0
                current_path["left"].append((current_x - plinko_width/2, funnel_y))
                current_path["right"].append((current_x + plinko_width/2, funnel_y))
                
                # Peg board
                peg_y = funnel_y - drop
                current_path["left"].append((current_x - plinko_width/2, peg_y))
                current_path["right"].append((current_x + plinko_width/2, peg_y))
                
                # Funnel close
                neck_y = peg_y - 3.0
                current_path["left"].append((current_x - 1.75, neck_y))
                current_path["right"].append((current_x + 1.75, neck_y))
                
                # Register pegs
                pegs_to_create.append({
                    "center_x": current_x,
                    "y_start": funnel_y - 1.5,
                    "y_end": peg_y + 1.5,
                    "width": plinko_width
                })
                
                current_y = neck_y
                direction = random.choice([1, -1])
                
            elif seg_type == "portal":
                # Create a clean cup directly at the end of the current slope
                cup_y = current_y - 3.0
                
                if direction == 1:
                    # Going right: right wall acts as a backboard to catch fast marbles
                    current_path["left"].append((current_x - 1.75, cup_y))
                    current_path["right"].append((current_x + 1.75, current_y + 2.0))
                    current_path["right"].append((current_x + 1.75, cup_y))
                else:
                    # Going left: left wall acts as a backboard
                    current_path["left"].append((current_x - 1.75, current_y + 2.0))
                    current_path["left"].append((current_x - 1.75, cup_y))
                    current_path["right"].append((current_x + 1.75, cup_y))
                    
                current_path["cap_end"] = True
                
                portal_a_pos = (current_x, cup_y + 1.0)
                
                # Portal B start
                portal_b_offset_x = random.uniform(-20.0, 20.0)
                portal_b_offset_y = random.uniform(-15.0, -25.0)
                portal_b_pos = (current_x + portal_b_offset_x, cup_y + portal_b_offset_y)
                
                # Start new path under Portal B
                new_path = {
                    "left": [
                        (portal_b_pos[0] - 2.5, portal_b_pos[1] + 1.0),
                        (portal_b_pos[0] + direction * 2.0 - 1.75, portal_b_pos[1] - 1.5)
                    ],
                    "right": [
                        (portal_b_pos[0] + 2.5, portal_b_pos[1] + 1.0),
                        (portal_b_pos[0] + direction * 2.0 + 1.75, portal_b_pos[1] - 1.5)
                    ],
                    "cap_start": False,
                    "cap_end": False
                }
                paths.append(new_path)
                current_path = new_path
                
                portals_to_create.append({
                    "pos_a": portal_a_pos,
                    "pos_b": portal_b_pos,
                    "color": get_y_color(cup_y)
                })
                
                current_x = portal_b_pos[0] + direction * 2.0
                current_y = portal_b_pos[1] - 1.5
                direction = -direction
                
            elif seg_type == "conveyor_slope":
                width = random.uniform(14.0, 20.0)
                climb = random.uniform(-2.0, 3.0) # can go uphill!
                
                next_x = current_x + direction * width
                next_y = current_y + climb
                
                current_path["left"].append((next_x - 1.75, next_y))
                current_path["right"].append((next_x + 1.75, next_y))
                
                # Add conveyor belt exactly on the floor segment
                if direction == 1:
                    cp1 = (current_x - 1.75, current_y)
                    cp2 = (next_x - 1.75, next_y)
                else:
                    cp1 = (current_x + 1.75, current_y)
                    cp2 = (next_x + 1.75, next_y)
                    
                physics_manager.add_conveyor(p1=cp1, p2=cp2, speed=8.0, color=(0, 180, 255))
                conveyor_lines.add(get_key(cp1, cp2))
                
                turn_y = next_y - 3.0
                current_path["left"].append((next_x - 1.75, turn_y))
                current_path["right"].append((next_x + 1.75, turn_y))
                
                current_x = next_x
                current_y = turn_y
                direction = -direction
                
            elif seg_type == "seesaw_drop":
                width = 10.0
                drop = 8.0
                
                funnel_y = current_y - 2.0
                current_path["left"].append((current_x - width/2, funnel_y))
                current_path["right"].append((current_x + width/2, funnel_y))
                
                # Seesaw in the center
                ss_pos = (current_x, funnel_y - 2.2)
                physics_manager.add_seesaw(pos=ss_pos, length=6.0, thickness=0.3, color=(255, 230, 0))
                
                neck_y = funnel_y - drop
                current_path["left"].append((current_x - 1.75, neck_y))
                current_path["right"].append((current_x + 1.75, neck_y))
                
                current_y = neck_y
                direction = random.choice([1, -1])
                
            elif seg_type == "spinners":
                width = 10.0
                drop = 12.0
                
                funnel_y = current_y - 2.0
                current_path["left"].append((current_x - width/2, funnel_y))
                current_path["right"].append((current_x + width/2, funnel_y))
                
                floor_y = funnel_y - drop
                current_path["left"].append((current_x - width/2, floor_y))
                current_path["right"].append((current_x + width/2, floor_y))
                
                # Safe tri-spinner layout with adequate gaps
                physics_manager.add_spinner(pos=(current_x, funnel_y - 3.0), radius=2.0, num_blades=4, is_motorized=True, motor_speed=3.0, color=(0, 255, 255))
                physics_manager.add_spinner(pos=(current_x - 2.2, funnel_y - 7.5), radius=1.6, num_blades=3, is_motorized=False, color=(255, 0, 100))
                physics_manager.add_spinner(pos=(current_x + 2.2, funnel_y - 7.5), radius=1.6, num_blades=5, is_motorized=True, motor_speed=-4.0, color=(0, 255, 100))
                
                neck_y = floor_y - 3.0
                current_path["left"].append((current_x - 1.75, neck_y))
                current_path["right"].append((current_x + 1.75, neck_y))
                
                current_y = neck_y
                direction = random.choice([1, -1])
                
            elif seg_type == "elevator_lift":
                lift_height = 10.0
                cup_y = current_y - 3.0
                current_path["left"].append((current_x - 1.75, cup_y))
                current_path["right"].append((current_x + 1.75, cup_y))
                current_path["cap_end"] = True
                
                # Solid block elevator prevents marbles from falling underneath
                elev_pos = (current_x, cup_y - lift_height / 2.0 + 0.1)
                physics_manager.add_elevator(pos=elev_pos, width=3.0, height=lift_height, travel_distance=lift_height, speed=3.5, color=(255, 165, 0))
                
                top_y = cup_y + lift_height
                
                # Solid side walls to contain marbles inside the elevator shaft
                if direction == 1:
                    physics_manager.add_wall(p1=(current_x - 1.6, cup_y + 1.0), p2=(current_x - 1.6, top_y + 2.0), friction=0.05, color=(100, 100, 255))
                    physics_manager.add_wall(p1=(current_x + 1.6, cup_y), p2=(current_x + 1.6, top_y), friction=0.05, color=(100, 100, 255))
                else:
                    physics_manager.add_wall(p1=(current_x - 1.6, cup_y), p2=(current_x - 1.6, top_y), friction=0.05, color=(100, 100, 255))
                    physics_manager.add_wall(p1=(current_x + 1.6, cup_y + 1.0), p2=(current_x + 1.6, top_y + 2.0), friction=0.05, color=(100, 100, 255))
                
                # Deflector at top to push marbles onto the new path
                if direction == 1:
                    physics_manager.add_wall(p1=(current_x - 1.2, top_y + 1.6), p2=(current_x + 1.2, top_y + 0.6), friction=0.05, color=(255, 100, 255))
                else:
                    physics_manager.add_wall(p1=(current_x + 1.2, top_y + 1.6), p2=(current_x - 1.2, top_y + 0.6), friction=0.05, color=(255, 100, 255))
                    
                next_x = current_x + direction * 4.0
                
                new_path = {
                    "left": [
                        (current_x - 2.0, top_y + 2.0),
                        (current_x - 2.0, top_y - 0.5),
                        (next_x - 1.75, top_y - 2.0)
                    ],
                    "right": [
                        (current_x + 2.0, top_y + 2.0),
                        (current_x + 2.0, top_y - 0.5),
                        (next_x + 1.75, top_y - 2.0)
                    ],
                    "cap_start": False,
                    "cap_end": False
                }
                paths.append(new_path)
                current_path = new_path
                
                current_x = next_x
                current_y = top_y - 2.0
                direction = -direction
                
            elif seg_type == "arena":
                arena_width = 16.0
                arena_drop = 12.0
                
                funnel_y = current_y - 4.0
                current_path["left"].append((current_x - arena_width/2, funnel_y))
                current_path["right"].append((current_x + arena_width/2, funnel_y))
                
                floor_y = funnel_y - arena_drop
                current_path["left"].append((current_x - arena_width/2, floor_y))
                current_path["right"].append((current_x + arena_width/2, floor_y))
                current_path["cap_end"] = True
                
                arena_bumpers_to_create.append({
                    "center_x": current_x,
                    "y_start": funnel_y - 2.0,
                    "y_end": floor_y + 2.0,
                    "width": arena_width
                })
                
                finish_lines_to_create.append({
                    "p1": (current_x - arena_width/2 + 1.0, floor_y + 0.8),
                    "p2": (current_x + arena_width/2 - 1.0, floor_y + 0.8)
                })
                
        # --- GENERATE PHYSICAL WALLS ---
        for path in paths:
            left_pts = path["left"]
            right_pts = path["right"]
            
            # Left walls
            for i in range(len(left_pts) - 1):
                p1 = left_pts[i]
                p2 = left_pts[i+1]
                if get_key(p1, p2) in conveyor_lines:
                    continue # skip static wall since conveyor is placed here
                mid_y = (p1[1] + p2[1]) / 2.0
                physics_manager.add_wall(p1=p1, p2=p2, friction=0.03, color=get_y_color(mid_y))
                
            # Right walls
            for i in range(len(right_pts) - 1):
                p1 = right_pts[i]
                p2 = right_pts[i+1]
                if get_key(p1, p2) in conveyor_lines:
                    continue # skip static wall since conveyor is placed here
                mid_y = (p1[1] + p2[1]) / 2.0
                physics_manager.add_wall(p1=p1, p2=p2, friction=0.03, color=get_y_color(mid_y))
                
            # Cap start
            if path["cap_start"]:
                p1 = left_pts[0]
                p2 = right_pts[0]
                physics_manager.add_wall(p1=p1, p2=p2, friction=0.1, color=get_y_color(p1[1]))
                
            # Cap end
            if path["cap_end"]:
                p1 = left_pts[-1]
                p2 = right_pts[-1]
                physics_manager.add_wall(p1=p1, p2=p2, friction=0.1, color=get_y_color(p1[1]))
                
        # --- CREATE CHILD ENTITIES ---
        # 1. Portals
        for req in portals_to_create:
            physics_manager.add_portal(pos_a=req["pos_a"], pos_b=req["pos_b"], radius=1.0, color=req["color"])
            
        # 2. Plinko Pegs
        for req in pegs_to_create:
            cx = req["center_x"]
            y_start = req["y_start"]
            y_end = req["y_end"]
            w = req["width"]
            
            peg_spacing_y = 2.4
            peg_spacing_x = 2.0
            rows = int((y_start - y_end) / peg_spacing_y)
            for r in range(rows):
                y_pos = y_start - r * peg_spacing_y
                cols = int((w - 2.0) / peg_spacing_x)
                start_x = cx - (cols - 1) * peg_spacing_x / 2.0
                if r % 2 == 1:
                    start_x += peg_spacing_x / 2.0
                    cols -= 1
                for c in range(cols):
                    x_pos = start_x + c * peg_spacing_x
                    physics_manager.add_box(
                        pos=(x_pos, y_pos),
                        width=0.4, height=0.4,
                        angle=math.pi / 4.0, # diamond
                        is_dynamic=False,
                        friction=0.05,
                        elasticity=0.8,
                        color=(255, 80, 80)
                    )
                    
        # 3. Arena Bumpers
        for req in arena_bumpers_to_create:
            cx = req["center_x"]
            y_start = req["y_start"]
            y_end = req["y_end"]
            w = req["width"]
            
            rows = 3
            dy_step = (y_start - y_end) / (rows + 1)
            for r in range(rows):
                y_pos = y_start - (r + 1) * dy_step
                if r % 2 == 0:
                    xs = [cx - w/4, cx, cx + w/4]
                else:
                    xs = [cx - w/6, cx + w/6]
                for bx in xs:
                    physics_manager.add_box(
                        pos=(bx, y_pos),
                        width=0.8, height=0.8,
                        angle=0.0,
                        is_dynamic=False,
                        friction=0.1,
                        elasticity=1.4,
                        color=(255, 0, 150)
                    )
                    
        # 4. Finish Lines
        for req in finish_lines_to_create:
            physics_manager.add_finish_line(p1=req["p1"], p2=req["p2"])
            
        return True

