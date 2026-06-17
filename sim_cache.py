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
        b = ss["body"]; bodies[ss["uid"]] = (b.position.x, b.position.y, b.angle)
    for sp in physics.spinners:
        b = sp["body"]; bodies[sp["uid"]] = (b.position.x, b.position.y, b.angle)
    for el in physics.elevators:
        b = el["body"]; bodies[el["uid"]] = (b.position.x, b.position.y, b.angle)
    return {"marbles": marbles, "bodies": bodies}


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


def draw_snapshot(surface, glow, cam, physics, snapshot, marble_table, sim_time):
    """Draw a scene from a cached snapshot instead of live physics transforms.

    Statics (walls, boosters, portals, finish lines, conveyors, escalators,
    spawners) are drawn from the physics object — they never move.
    Dynamic bodies (boxes, seesaws, spinners, elevators, marbles) are drawn
    from the snapshot transforms.
    """
    # A. Background
    surface.fill(UITheme.BG_DARK_SOLID)

    # --- Statics copied verbatim from render_physics_scene ---

    # Draw portals
    for portal in physics.portals:
        draw_neon_circle(surface, portal['pos_a'], portal['radius'], portal['color'], width=2, camera=cam, glow_surf=glow)
        draw_neon_circle(surface, portal['pos_b'], portal['radius'], portal['color'], width=2, camera=cam, glow_surf=glow)

    # Draw finish lines
    for finish in physics.finish_lines:
        draw_neon_line(surface, finish['p1'], finish['p2'], finish['color'], 4, cam, glow_surf=glow)

    # Draw boosters
    for booster in physics.boosters:
        draw_neon_line(surface, booster['p1'], booster['p2'], booster['color'], 5, cam, glow_surf=glow)
        cx = (booster['p1'][0] + booster['p2'][0]) / 2.0
        cy = (booster['p1'][1] + booster['p2'][1]) / 2.0
        dx = booster['direction'][0] * 0.4
        dy = booster['direction'][1] * 0.4
        draw_neon_line(surface, (cx, cy), (cx + dx, cy + dy), booster['color'], 2, cam, glow_surf=glow)

    # Draw walls
    for wall in physics.walls:
        draw_neon_line(surface, wall.a, wall.b, wall.color, 3, cam, glow_surf=glow)

    # Draw conveyors
    for conv in physics.conveyors:
        draw_neon_line(surface, conv['p1'], conv['p2'], conv['color'], 5, cam, glow_surf=glow)
        p1_scr = cam.world_to_screen(conv['p1'])
        p2_scr = cam.world_to_screen(conv['p2'])
        dx = p2_scr[0] - p1_scr[0]
        dy = p2_scr[1] - p1_scr[1]
        length = math.hypot(dx, dy)
        if length > 0:
            ux = dx / length
            uy = dy / length

            # Sync conveyor dots visual movement speed with physical conveyor speed
            step_size_world = 0.5  # spacing of conveyor dots in world units
            offset_world = (sim_time * conv['speed']) % step_size_world
            offset = offset_world * cam.zoom
            step_size_scr = max(4.0, step_size_world * cam.zoom)

            d = offset
            while d < length:
                px = p1_scr[0] + ux * d
                py = p1_scr[1] + uy * d
                pygame.draw.circle(surface, (255, 255, 255), (int(px), int(py)), 3)
                d += step_size_scr

    # Draw escalators
    for esc in physics.escalators:
        p1_scr = cam.world_to_screen(esc['p1'])
        p2_scr = cam.world_to_screen(esc['p2'])

        # During playback treat it as running — draw muted guide line
        pygame.draw.line(surface, (50, 60, 75), p1_scr, p2_scr, 1)

        steps = esc.get('steps', [])
        for body, tread, riser in steps:
            # Get world coordinates of tread endpoints (physically clipped in Pymunk)
            ta_w = body.local_to_world(tread.a)
            tb_w = body.local_to_world(tread.b)

            if math.hypot(ta_w.x - tb_w.x, ta_w.y - tb_w.y) > 0.02:
                ta = cam.world_to_screen(ta_w)
                tb = cam.world_to_screen(tb_w)
                pygame.draw.line(surface, (255, 255, 255), ta, tb, 2)

            # Get world coordinates of riser endpoints (physically clipped in Pymunk)
            ra_w = body.local_to_world(riser.a)
            rb_w = body.local_to_world(riser.b)

            if math.hypot(ra_w.x - rb_w.x, ra_w.y - rb_w.y) > 0.02:
                ra = cam.world_to_screen(ra_w)
                rb = cam.world_to_screen(rb_w)
                pygame.draw.line(surface, (255, 255, 255), ra, rb, 2)

    # Draw Spawners
    for spawner in physics.spawners:
        draw_neon_circle(surface, spawner['pos'], 0.7, spawner['color'], width=1, camera=cam, glow_surf=glow)
        scr_center = cam.world_to_screen(spawner['pos'])
        pygame.draw.circle(surface, spawner['color'], scr_center, 6)

    # --- Dynamic bodies from snapshot transforms ---
    bodies = snapshot["bodies"]

    # Draw boxes (static boxes use their own live transform; dynamic boxes use snapshot)
    for box in physics.boxes:
        if not getattr(box, "is_dynamic", False) or box.uid not in bodies:
            bx = box.body.position.x
            by = box.body.position.y
            ba = box.body.angle
        else:
            bx, by, ba = bodies[box.uid]
        _draw_poly_body(surface, glow, cam, box.width, box.height, bx, by, ba, box.color)

    # Draw elevators from snapshot transform
    for elev in physics.elevators:
        uid = elev['uid']
        if uid in bodies:
            ex, ey, ea = bodies[uid]
        else:
            b = elev['body']
            ex, ey, ea = b.position.x, b.position.y, b.angle
        w_half = elev['width'] / 2.0
        h_half = elev['height'] / 2.0
        rx_cos, rx_sin = math.cos(ea), math.sin(ea)
        ux_cos, ux_sin = -math.sin(ea), math.cos(ea)
        local_verts = [(-w_half, -h_half), (w_half, -h_half), (w_half, h_half), (-w_half, h_half)]
        world_verts = [(ex + lx * rx_cos + ly * ux_cos, ey + lx * rx_sin + ly * ux_sin)
                       for (lx, ly) in local_verts]
        scr_verts = [cam.world_to_screen(wv) for wv in world_verts]
        pygame.draw.polygon(surface, (*elev['color'], 80), scr_verts)
        for i in range(len(world_verts)):
            p1 = world_verts[i]
            p2 = world_verts[(i + 1) % len(world_verts)]
            draw_neon_line(surface, p1, p2, elev['color'], 3, cam, glow_surf=glow)
        p_ctr = cam.world_to_screen((ex, ey))
        w_scr = int(elev['width'] * cam.zoom)
        pygame.draw.line(surface, (255, 255, 255), (p_ctr[0] - w_scr // 2, p_ctr[1]), (p_ctr[0] + w_scr // 2, p_ctr[1]), 1)

    # Draw seesaws from snapshot transform
    for ss in physics.seesaws:
        uid = ss['uid']
        if uid in bodies:
            sx, sy, sa = bodies[uid]
        else:
            b = ss['body']
            sx, sy, sa = b.position.x, b.position.y, b.angle
        w_half = ss['length'] / 2.0
        h_half = ss['thickness'] / 2.0
        rx_cos, rx_sin = math.cos(sa), math.sin(sa)
        ux_cos, ux_sin = -math.sin(sa), math.cos(sa)
        local_verts = [(-w_half, -h_half), (w_half, -h_half), (w_half, h_half), (-w_half, h_half)]
        world_verts = [(sx + lx * rx_cos + ly * ux_cos, sy + lx * rx_sin + ly * ux_sin)
                       for (lx, ly) in local_verts]
        scr_verts = [cam.world_to_screen(wv) for wv in world_verts]
        pygame.draw.polygon(surface, (*ss['color'], 100), scr_verts)
        for i in range(len(world_verts)):
            p1 = world_verts[i]
            p2 = world_verts[(i + 1) % len(world_verts)]
            draw_neon_line(surface, p1, p2, ss['color'], 3, cam, glow_surf=glow)
        scr_pivot = cam.world_to_screen(ss['pos'])
        pygame.draw.circle(surface, (255, 255, 255), scr_pivot, 4)

    # Draw spinners from snapshot transform
    for sp in physics.spinners:
        uid = sp['uid']
        if uid in bodies:
            spx, spy, spa = bodies[uid]
        else:
            b = sp['body']
            spx, spy, spa = b.position.x, b.position.y, b.angle
        rx_cos, rx_sin = math.cos(spa), math.sin(spa)
        ux_cos, ux_sin = -math.sin(spa), math.cos(spa)
        for shape in sp['shapes']:
            local_verts = shape.get_vertices()
            # Apply body rotation to local verts (shape verts are in body-local space)
            world_verts = [(spx + lx * rx_cos + ly * ux_cos, spy + lx * rx_sin + ly * ux_sin)
                           for (lx, ly) in local_verts]
            scr_verts = [cam.world_to_screen(wv) for wv in world_verts]
            pygame.draw.polygon(surface, (*sp['color'], 100), scr_verts)
            for i in range(len(world_verts)):
                p1 = world_verts[i]
                p2 = world_verts[(i + 1) % len(world_verts)]
                draw_neon_line(surface, p1, p2, sp['color'], 2, cam, glow_surf=glow)
        scr_pivot = cam.world_to_screen(sp['pos'])
        pygame.draw.circle(surface, (255, 255, 255), scr_pivot, 5)

    # Blit glow layer
    surface.blit(glow, (0, 0))

    # Draw marbles from snapshot
    for (uid, x, y, ang) in snapshot["marbles"]:
        if uid not in marble_table:
            continue
        radius, color = marble_table[uid]
        center = cam.world_to_screen((x, y))
        rad = int(radius * cam.zoom)
        if rad > 0:
            pygame.draw.circle(surface, color, center, rad)
            pygame.draw.circle(surface, (255, 255, 255), center, rad, width=1)
            rx = radius * math.cos(ang)
            ry = radius * math.sin(ang)
            edge_pos = (x + rx, y + ry)
            edge_scr = cam.world_to_screen(edge_pos)
            pygame.draw.line(surface, (0, 0, 0), center, edge_scr, 2)
