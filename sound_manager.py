import pygame
import os
import wave
import numpy as np
import random
import math

class SoundManager:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SoundManager()
        return cls._instance
        
    def __init__(self):
        self.enabled = False
        self.recorded_events = []
        self.recording = False
        self.current_time = 0.0
        
        # Spatial sound parameters
        self.camera_pos = (0.0, 0.0)
        self.view_half_width = 20.0  # approximate half-width of the view in world units
        
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.enabled = True
        except Exception as e:
            print(f"Failed to initialize Pygame mixer: {e}")
            return
            
        base_dir = "D:/Projects/2026/Python/Marbles/sounds"
        self.sounds = {}
        self.raw_sound_data = {}
        self.pitch_variations = {}
        
        wav_files = {
            "marble_marble": "marble_marble.wav",
            "marble_wall": "marble_wall.wav",
            "marble_box": "marble_box.wav",
            "portal": "portal.wav",
            "finish": "finish.wav"
        }
        
        # Pitch factors to pre-generate for real-time play (minimizes runtime CPU load)
        self.pitch_factors = [0.85, 0.90, 0.95, 1.0, 1.05, 1.10, 1.15]
        
        for name, filename in wav_files.items():
            path = os.path.join(base_dir, filename)
            if os.path.exists(path):
                # Load raw data for processing
                raw_data, rate, channels = self._load_raw_wav(path)
                if raw_data is not None:
                    self.raw_sound_data[name] = raw_data
                    
                    # Pre-generate pitch variations for real-time play
                    self.pitch_variations[name] = []
                    for factor in self.pitch_factors:
                        resampled = self._resample(raw_data, factor)
                        sound_obj = self._make_pygame_sound(resampled)
                        if sound_obj is not None:
                            self.pitch_variations[name].append((factor, sound_obj))
                    
                    # Store standard sound as fallback
                    try:
                        self.sounds[name] = pygame.mixer.Sound(path)
                    except:
                        if self.pitch_variations[name]:
                            # Use the 1.0 factor variation
                            self.sounds[name] = min(self.pitch_variations[name], key=lambda x: abs(x[0] - 1.0))[1]
            else:
                print(f"Sound file not found: {path}")
                
        if not self.sounds:
            self.enabled = False

    def _load_raw_wav(self, path):
        """Loads a WAV file and returns its stereo interleaved data, rate, and channels."""
        try:
            with wave.open(path, 'rb') as w:
                nchannels = w.getnchannels()
                sampwidth = w.getsampwidth()
                framerate = w.getframerate()
                raw_data = w.readframes(w.getnframes())
                
                if sampwidth == 2:
                    data = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                elif sampwidth == 1:
                    data = (np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
                else:
                    return None, None, None
                    
                # Convert to stereo interleaved
                if nchannels == 1:
                    data_stereo = np.column_stack((data, data)).flatten()
                elif nchannels == 2:
                    data_stereo = data
                else:
                    return None, None, None
                    
                return data_stereo, framerate, 2
        except Exception as e:
            print(f"Error reading raw WAV {path}: {e}")
            return None, None, None

    def _resample(self, data_stereo, factor):
        """Resamples stereo interleaved data by a playback speed factor (pitch shift)."""
        if factor == 1.0 or len(data_stereo) < 4:
            return data_stereo.copy()
            
        left = data_stereo[0::2]
        right = data_stereo[1::2]
        
        old_indices = np.arange(len(left))
        # Determine new indices based on the pitch factor
        new_indices = np.arange(0, len(left) - 1, factor)
        
        left_resampled = np.interp(new_indices, old_indices, left)
        right_resampled = np.interp(new_indices, old_indices, right)
        
        # Re-interleave stereo channels
        return np.column_stack((left_resampled, right_resampled)).flatten()

    def _make_pygame_sound(self, data_stereo):
        """Converts stereo float32 data into a Pygame Sound object."""
        # Convert back to 16-bit PCM buffer
        pcm_data = (np.clip(data_stereo, -1.0, 1.0) * 32767.0).astype(np.int16)
        try:
            return pygame.mixer.Sound(buffer=pcm_data.tobytes())
        except Exception as e:
            try:
                import pygame.sndarray
                pcm_stereo = pcm_data.reshape(-1, 2)
                return pygame.sndarray.make_sound(pcm_stereo)
            except Exception as e2:
                print(f"Failed to create Pygame sound: {e}, {e2}")
                return None

    def calculate_doppler_and_pan(self, pos, vel):
        """Calculates Doppler pitch adjustment and stereo pan factor based on source pos and vel."""
        if pos is None:
            return 1.0, 0.0
            
        # Panning (-1.0 to 1.0)
        dx = pos[0] - self.camera_pos[0]
        pan = dx / self.view_half_width
        pan = max(-1.0, min(1.0, pan))
        
        # Doppler pitch shifting
        pitch = 1.0
        if vel is not None:
            dy = pos[1] - self.camera_pos[1]
            dist = math.hypot(dx, dy)
            if dist > 0.0:
                # Calculate velocity component along radial direction to camera
                v_rel = (vel[0] * dx + vel[1] * dy) / dist
                c_sound = 60.0  # Speed of sound in simulation coordinates
                doppler_factor = 1.0 - (v_rel / c_sound)
                pitch = max(0.85, min(1.15, doppler_factor))
                
        return pitch, pan

    def play(self, name, volume=1.0, pos=None, vel=None):
        """Plays a sound with dynamic volume, stereo panning, and pitch variations."""
        pitch_factor, pan_factor = self.calculate_doppler_and_pan(pos, vel)
        
        # Subtle pitch randomization to completely eliminate the machinegun effect
        random_pitch = random.uniform(0.96, 1.04)
        final_pitch = pitch_factor * random_pitch
        
        # Log sound event details if recording is active
        if self.recording:
            self.recorded_events.append({
                'name': name,
                'volume': volume,
                'time': self.current_time,
                'pitch': final_pitch,
                'pan': pan_factor
            })
            
        if not self.enabled:
            return
            
        # Retrieve the closest pre-generated pitch shifted sound
        sound_to_play = None
        if name in self.pitch_variations and self.pitch_variations[name]:
            sound_to_play = min(self.pitch_variations[name], key=lambda x: abs(x[0] - final_pitch))[1]
        elif name in self.sounds:
            sound_to_play = self.sounds[name]
            
        if sound_to_play is None:
            return
            
        try:
            clamped_volume = max(0.0, min(1.0, volume))
            
            # Constant power panning to keep audio power consistent as it moves
            angle = (pan_factor + 1.0) * (math.pi / 4.0)
            left_gain = math.cos(angle)
            right_gain = math.sin(angle)
            
            channel = sound_to_play.play()
            if channel is not None:
                channel.set_volume(clamped_volume * left_gain, clamped_volume * right_gain)
        except Exception as e:
            print(f"Error playing sound {name}: {e}")
            
    def play_impact(self, collision_type, impulse_magnitude, pos=None, vel=None):
        """Plays a collision sound scaled by impact magnitude, with 3D spatial pan and pitch variation."""
        min_threshold = 1.2
        if impulse_magnitude < min_threshold:
            return
            
        # Apply a non-linear power volume curve (1.5 power scale)
        # This makes rolling sounds / light bumps significantly softer, boosting realism
        normalized_impulse = min(1.0, (impulse_magnitude - min_threshold) / 10.0)
        volume = normalized_impulse ** 1.5
        
        if collision_type == "marble_marble":
            self.play("marble_marble", volume * 0.9, pos, vel)
        elif collision_type == "marble_wall":
            self.play("marble_wall", volume * 1.0, pos, vel)
        elif collision_type == "marble_box":
            self.play("marble_box", volume * 0.95, pos, vel)

    def start_recording(self):
        """Starts recording sound events."""
        self.recorded_events = []
        self.recording = True
        self.current_time = 0.0
        print("Sound recording started.")

    def stop_recording(self, output_wav_path, duration_sec):
        """Stops recording sound events and mixes them into a WAV file."""
        self.recording = False
        self.save_wav_recording(output_wav_path, duration_sec)

    def save_wav_recording(self, output_wav_path, duration_sec):
        """Mixes all recorded sound events into a single WAV file applying exact pitch and panning."""
        total_samples = int(duration_sec * 44100)
        output_data = np.zeros(total_samples * 2, dtype=np.float32)
        
        for event in self.recorded_events:
            name = event['name']
            volume = event['volume']
            time = event['time']
            pitch = event.get('pitch', 1.0)
            pan = event.get('pan', 0.0)
            
            if name in self.raw_sound_data:
                # 1. Resample raw sound by the exact event pitch factor
                raw_stereo = self.raw_sound_data[name]
                resampled_stereo = self._resample(raw_stereo, pitch)
                
                # 2. Apply constant power panning
                left = resampled_stereo[0::2]
                right = resampled_stereo[1::2]
                
                angle = (pan + 1.0) * (math.pi / 4.0)
                left_gain = math.cos(angle)
                right_gain = math.sin(angle)
                
                left_panned = left * left_gain * volume
                right_panned = right * right_gain * volume
                
                panned_stereo = np.column_stack((left_panned, right_panned)).flatten()
                
                # 3. Add to output mix buffer
                start_sample = int(time * 44100) * 2
                sound_len = len(panned_stereo)
                end_sample = min(start_sample + sound_len, len(output_data))
                add_len = end_sample - start_sample
                
                if add_len > 0:
                    output_data[start_sample:end_sample] += panned_stereo[:add_len]
                    
        # Clip output to prevent digital distortion and convert to 16-bit PCM WAV
        output_data = np.clip(output_data, -1.0, 1.0)
        output_pcm = (output_data * 32767.0).astype(np.int16)
        
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)
            with wave.open(output_wav_path, 'wb') as w:
                w.setnchannels(2)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(output_pcm.tobytes())
            print(f"Audio track compiled successfully: {output_wav_path}")
        except Exception as e:
            print(f"Error saving mixed WAV file: {e}")
