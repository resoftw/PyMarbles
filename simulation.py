import pygame
import math
from ui import UITheme, draw_neon_line, draw_neon_circle

class Simulation:
    def __init__(self, physics_manager, camera, video_exporter):
        self.physics = physics_manager
        self.camera = camera
        self.exporter = video_exporter
        
        self.running = False
        self.sim_time = 0.0
        self.dt = 1.0 / 60.0
        self.speed_multiplier = 1.0 # 0.5x, 1x, 2x, etc.
        
        # Camera mode: "free", "leader"
        self.camera_mode = "free"
        
        # Standings (marbles that crossed finish line or leading marbles)
        self.leaderboard = []
        self.crossed_count = 0

    def start(self):
        """Initializes/Resets and starts the simulation."""
        self.running = True
        self.sim_time = 0.0
        
        # Reset spawners
        for spawner in self.physics.spawners:
            spawner['spawned'] = 0
            spawner['last_spawn_time'] = -spawner['rate']
            
        # Clear existing marbles
        for marble in list(self.physics.marbles):
            self.physics.space.remove(marble.body, marble)
        self.physics.marbles.clear()
        
        # Reset finish lines
        for finish in self.physics.finish_lines:
            finish['crossed_marbles'].clear()
            
        self.leaderboard.clear()

    def stop(self):
        """Pauses/Stops simulation."""
        self.running = False
        # Silence the continuous rolling bed when the race is paused/stopped
        from sound_manager import SoundManager
        SoundManager.get_instance().update_rolling([])

    def update(self):
        """Updates physics space, spawners, trails, and leaderboard."""
        if not self.running:
            return
            
        # Divide each physics step into 4 substeps (240Hz physics) to prevent tunneling of fast marbles
        substeps = 4
        
        # Calculate step count based on speed multiplier
        steps = int(self.speed_multiplier)
        if self.speed_multiplier < 1.0:
            steps = 1
            
        # Calculate time step size per substep
        step_size = (self.dt * self.speed_multiplier) / substeps if self.speed_multiplier < 1.0 else self.dt / substeps
        
        from sound_manager import SoundManager
        sound_mgr = SoundManager.get_instance()
        
        for _ in range(steps * substeps):
            # Spawn new marbles if ready
            self.physics.update_spawners(self.sim_time)
            
            # Sync SoundManager time for audio recording
            if sound_mgr.recording:
                sound_mgr.current_time = self.sim_time
                
            # Step the Pymunk space
            self.physics.step(step_size)
            
            # Update simulation time
            self.sim_time += step_size
            
        # Update trails once per frame
        self._update_marble_trails()

        # Drive the continuous rolling rumble from current marble activity
        sound_mgr.update_rolling(self.physics.marbles)

        # Update Leaderboard standings
        self._update_leaderboard()
        
        # Update camera if in follow mode
        if self.camera_mode == "leader" and self.physics.marbles:
            leader = self.get_leader()
            if leader:
                self.camera.follow(leader.body.position, lerp_speed=0.08)

    def _update_marble_trails(self):
        """Maintains trailing trail history for all marbles."""
        for marble in self.physics.marbles:
            pos = (marble.body.position.x, marble.body.position.y)
            # Add to trail
            marble.trail.append(pos)
            if len(marble.trail) > 15:
                marble.trail.pop(0)

    def _update_leaderboard(self):
        """Computes current race standings."""
        # Leaderboard consists of:
        # 1. Marbles that crossed the finish line (sorted by crossing time)
        # 2. Remaining active marbles sorted by lowest Y coordinate (since they roll downwards)
        
        crossed = []
        # Gather all marbles that crossed any finish line
        for finish in self.physics.finish_lines:
            for marble in finish['crossed_marbles']:
                if marble not in crossed:
                    crossed.append(marble)
                    
        # Active marbles (not yet crossed)
        active_marbles = [m for m in self.physics.marbles if m not in crossed]
        # Sort active marbles by lowest Y (since Y points up in Pymunk, lower Y means further down the track)
        active_marbles.sort(key=lambda m: m.body.position.y)
        
        # Combine
        self.leaderboard = crossed + active_marbles
        self.crossed_count = len(crossed)

    def get_leader(self):
        """Returns the current leader marble shape."""
        if self.leaderboard:
            return self.leaderboard[0]
        return None

    def draw_trails(self, surface, glow_surf):
        """Draws fading neon motion blur trails for all marbles."""
        for marble in self.physics.marbles:
            if len(marble.trail) < 2:
                continue
                
            color = marble.color
            # Draw lines between trail points with fading opacity directly onto the shared glow_surf
            for i in range(len(marble.trail) - 1):
                p1 = marble.trail[i]
                p2 = marble.trail[i+1]
                
                # Calculate alpha fading (older points are transparent)
                alpha = int(180 * (i / len(marble.trail)))
                if alpha <= 0:
                    continue
                    
                p1_scr = self.camera.world_to_screen(p1)
                p2_scr = self.camera.world_to_screen(p2)
                
                # Thickness scales slightly down for older parts of the trail
                thickness = max(1, int(marble.radius * self.camera.zoom * (i / len(marble.trail))))
                
                pygame.draw.line(glow_surf, (*color, alpha), p1_scr, p2_scr, thickness)

    def draw_hud(self, surface, font):
        """Draws standard race HUD: leaderboard standings, timer, speed control."""
        # Top-left HUD box
        # Position HUD next to Inspector (width - 300 - 260) to prevent overlap with toolbox
        hud_rect = pygame.Rect(surface.get_width() - 560, 80, 240, 220)
        pygame.draw.rect(surface, UITheme.BG_DARK, hud_rect, border_radius=8)
        pygame.draw.rect(surface, UITheme.BORDER, hud_rect, width=1, border_radius=8)
        
        # Title
        header_font = pygame.font.SysFont(UITheme.FONT_NAME, 16, bold=True)
        title_surf = header_font.render("LEADERBOARD STANDINGS", True, UITheme.ACCENT_CYAN)
        surface.blit(title_surf, (hud_rect.x + 15, hud_rect.y + 15))
        
        # Standings
        y_offset = 45
        for index, marble in enumerate(self.leaderboard[:5]): # Show top 5
            # Number circle color
            num_color = UITheme.ACCENT_CYAN if index == 0 else UITheme.TEXT_MUTED
            pos_text = font.render(f"#{index+1}", True, num_color)
            surface.blit(pos_text, (hud_rect.x + 15, hud_rect.y + y_offset))
            
            # Colored dot representing marble
            pygame.draw.circle(surface, marble.color, (hud_rect.x + 60, hud_rect.y + y_offset + 9), 6)
            
            # Speed/Time text
            if index < self.crossed_count:
                # Finished
                time_text = font.render("FINISHED", True, (0, 255, 100))
            else:
                # Active
                speed = math.hypot(marble.body.velocity.x, marble.body.velocity.y)
                time_text = font.render(f"{speed:.1f} m/s", True, UITheme.TEXT_LIGHT)
                
            surface.blit(time_text, (hud_rect.x + 85, hud_rect.y + y_offset))
            y_offset += 32
            
        # Time counter bottom of HUD
        time_text = font.render(f"Sim Time: {self.sim_time:.2f}s", True, UITheme.TEXT_MUTED)
        surface.blit(time_text, (hud_rect.x + 15, hud_rect.y + hud_rect.height - 30))
