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
            
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
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
        
        # Pitch factors to pre-generate for real-time play (minimizes runtime CPU load).
        # Fine 2.5% spacing across a wide range so the nearest-bucket snap is inaudible
        # (this is what kills the "machinegun" effect) while keeping playback allocation-free.
        self.pitch_factors = [round(0.80 + 0.025 * i, 3) for i in range(19)]  # 0.80 .. 1.25
        self.min_pitch = self.pitch_factors[0]
        self.max_pitch = self.pitch_factors[-1]
        
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

        # Continuous rolling bed: a single looped rumble channel whose volume/pan is
        # modulated every frame by aggregate rolling activity (see update_rolling).
        self.rolling_sound = None
        self.rolling_channel = None
        self.rolling_raw = None       # raw loop samples, for synthesizing into recordings
        self.rolling_envelope = []    # [{time, level, pan}] logged while recording
        self.rolling_master = 0.45    # overall loudness ceiling for the rolling bed
        if self.enabled:
            roll_path = os.path.join(base_dir, "rolling.wav")
            if os.path.exists(roll_path):
                try:
                    self.rolling_sound = pygame.mixer.Sound(roll_path)
                    self.rolling_raw, _, _ = self._load_raw_wav(roll_path)
                    # Reserve channel 0 so effect sounds never steal the rolling loop
                    pygame.mixer.set_reserved(1)
                    self.rolling_channel = pygame.mixer.Channel(0)
                    self.rolling_channel.play(self.rolling_sound, loops=-1)
                    self.rolling_channel.set_volume(0.0)
                except Exception as e:
                    print(f"Failed to start rolling bed: {e}")
                    self.rolling_channel = None

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

    def calculate_spatial(self, pos, vel):
        """Computes Doppler pitch, stereo pan, and distance attenuation gain for a
        sound source at world position `pos` moving at velocity `vel`, relative to
        the listener (camera). Returns (pitch, pan, distance_gain, distance)."""
        if pos is None:
            return 1.0, 0.0, 1.0, 0.0

        dx = pos[0] - self.camera_pos[0]
        dy = pos[1] - self.camera_pos[1]
        dist = math.hypot(dx, dy)

        # Panning (-1.0 .. 1.0) relative to the visible half-width (kept in sync with zoom)
        half_w = max(1e-3, self.view_half_width)
        pan = max(-1.0, min(1.0, dx / half_w))

        # Distance attenuation: sources at the center are full volume; loudness rolls
        # off smoothly so collisions far outside the viewport fade out naturally.
        ref = half_w * 1.5
        distance_gain = (ref * ref) / (ref * ref + dist * dist)

        # Doppler pitch shifting (radial velocity component toward/away from listener)
        pitch = 1.0
        if vel is not None and dist > 0.0:
            v_rel = (vel[0] * dx + vel[1] * dy) / dist
            c_sound = 60.0  # Speed of sound in simulation coordinates
            doppler_factor = 1.0 - (v_rel / c_sound)
            pitch = max(0.85, min(1.15, doppler_factor))

        return pitch, pan, distance_gain, dist

    def play(self, name, volume=1.0, pos=None, vel=None, base_pitch=1.0):
        """Plays a sound with dynamic volume, stereo panning, distance attenuation,
        Doppler shift, and per-hit pitch variation.

        base_pitch lets the caller couple pitch to physics (e.g. harder impacts
        ring slightly higher/brighter)."""
        doppler_pitch, pan_factor, distance_gain, distance = self.calculate_spatial(pos, vel)

        # Continuous per-hit pitch jitter so no two consecutive hits sound identical.
        # Because pitch buckets are now finely spaced, this variation survives the snap.
        random_pitch = random.uniform(0.95, 1.05)
        final_pitch = base_pitch * doppler_pitch * random_pitch
        final_pitch = max(self.min_pitch, min(self.max_pitch, final_pitch))

        final_volume = max(0.0, min(1.0, volume * distance_gain))

        # Log sound event details if recording is active (store post-spatialization
        # values so the offline mix matches what was heard live)
        if self.recording:
            self.recorded_events.append({
                'name': name,
                'volume': final_volume,
                'time': self.current_time,
                'pitch': final_pitch,
                'pan': pan_factor,
                'distance': distance
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
            # Constant power panning to keep audio power consistent as it moves
            angle = (pan_factor + 1.0) * (math.pi / 4.0)
            left_gain = math.cos(angle)
            right_gain = math.sin(angle)

            channel = sound_to_play.play()
            if channel is not None:
                channel.set_volume(final_volume * left_gain, final_volume * right_gain)
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

        # Harder impacts excite higher resonant modes: real collisions get brighter
        # and slightly higher in pitch with energy. Pitching the modal sample up
        # raises its spectral centroid, approximating that brightness shift.
        impact_pitch = 1.0 + 0.18 * normalized_impulse

        if collision_type == "marble_marble":
            self.play("marble_marble", volume * 0.9, pos, vel, base_pitch=impact_pitch)
        elif collision_type == "marble_wall":
            self.play("marble_wall", volume * 1.0, pos, vel, base_pitch=impact_pitch)
        elif collision_type == "marble_box":
            self.play("marble_box", volume * 0.95, pos, vel, base_pitch=impact_pitch)

    # Reference rolling rim speed (angular_velocity * radius) that maps to full intensity
    ROLL_SPEED_REF = 14.0

    def update_rolling(self, marbles):
        """Modulates the continuous rolling bed from aggregate marble activity.

        A marble's angular velocity is a good proxy for surface contact: marbles
        resting are still, free-falling marbles barely spin, but a marble rolling
        on a track spins proportionally to its travel. We sum that activity, then
        set the looped bed's volume, stereo pan, and distance falloff to match the
        activity-weighted centroid of the rolling marbles."""
        if not self.enabled:
            return

        total = 0.0
        cx = 0.0
        cy = 0.0
        for m in marbles:
            rim_speed = abs(m.body.angular_velocity) * m.radius
            roll = min(1.0, rim_speed / self.ROLL_SPEED_REF)
            if roll < 0.05:  # ignore near-stationary marbles
                continue
            total += roll
            cx += m.body.position.x * roll
            cy += m.body.position.y * roll

        if total <= 0.0:
            level = 0.0
            pan = 0.0
        else:
            centroid = (cx / total, cy / total)
            _, pan, distance_gain, _ = self.calculate_spatial(centroid, None)
            # Saturating curve so a crowd of marbles swells the bed without clipping
            activity = 1.0 - math.exp(-total * 0.45)
            level = activity * distance_gain * self.rolling_master

        # Log the envelope so the rolling bed can be synthesized into recordings
        if self.recording:
            self.rolling_envelope.append({'time': self.current_time, 'level': level, 'pan': pan})

        # Drive the live looped channel
        if self.rolling_channel is not None:
            angle = (pan + 1.0) * (math.pi / 4.0)
            self.rolling_channel.set_volume(level * math.cos(angle), level * math.sin(angle))

    def start_recording(self):
        """Starts recording sound events."""
        self.recorded_events = []
        self.rolling_envelope = []
        self.recording = True
        self.current_time = 0.0
        print("Sound recording started.")

    def stop_recording(self, output_wav_path, duration_sec):
        """Stops recording sound events and mixes them into a WAV file."""
        self.recording = False
        self.save_wav_recording(output_wav_path, duration_sec)

    def _lowpass_fft(self, x, cutoff_hz, sr=44100):
        """Applies a smooth (~6 dB/oct) low-pass to a mono signal via FFT. Used to
        model air absorption: distant impacts lose their high-frequency sparkle."""
        n = len(x)
        if n == 0 or cutoff_hz >= sr / 2.0:
            return x
        spectrum = np.fft.rfft(x)
        freqs = np.fft.rfftfreq(n, 1.0 / sr)
        response = 1.0 / (1.0 + (freqs / cutoff_hz) ** 2)
        return np.fft.irfft(spectrum * response, n=n).astype(np.float32)

    def _cutoff_for_distance(self, dist):
        """Maps source distance to a low-pass cutoff: near = bright, far = muffled."""
        return 2500.0 + (16000.0 - 2500.0) * math.exp(-dist / 15.0)

    def _mix_rolling_bed(self, output_data, total_samples, sr=44100):
        """Synthesizes the continuous rolling rumble into the recording mix by tiling
        the seamless loop and applying the per-frame level/pan envelope captured live."""
        if self.rolling_raw is None or len(self.rolling_envelope) < 2 or total_samples <= 0:
            return

        loop_left = self.rolling_raw[0::2]
        loop_right = self.rolling_raw[1::2]
        if len(loop_left) == 0:
            return

        n = total_samples
        reps = n // len(loop_left) + 1
        bed_left = np.tile(loop_left, reps)[:n]
        bed_right = np.tile(loop_right, reps)[:n]

        times = np.array([e['time'] for e in self.rolling_envelope], dtype=np.float64)
        levels = np.array([e['level'] for e in self.rolling_envelope], dtype=np.float64)
        pans = np.array([e['pan'] for e in self.rolling_envelope], dtype=np.float64)

        # Interpolate the frame-rate envelope up to per-sample resolution
        sample_times = np.arange(n) / float(sr)
        level_env = np.interp(sample_times, times, levels, left=0.0, right=0.0)
        pan_env = np.interp(sample_times, times, pans, left=pans[0], right=pans[-1])

        angle = (pan_env + 1.0) * (math.pi / 4.0)
        bed_left = bed_left * level_env * np.cos(angle)
        bed_right = bed_right * level_env * np.sin(angle)

        output_data[0::2] += bed_left.astype(np.float32)
        output_data[1::2] += bed_right.astype(np.float32)

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
            distance = event.get('distance', 0.0)

            if name in self.raw_sound_data:
                # 1. Resample raw sound by the exact event pitch factor
                raw_stereo = self.raw_sound_data[name]
                resampled_stereo = self._resample(raw_stereo, pitch)

                # 2. Apply constant power panning
                left = resampled_stereo[0::2]
                right = resampled_stereo[1::2]

                # 2b. Air absorption: muffle high frequencies for distant impacts
                if distance > 2.0:
                    cutoff = self._cutoff_for_distance(distance)
                    left = self._lowpass_fft(left, cutoff)
                    right = self._lowpass_fft(right, cutoff)

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

        # Synthesize the continuous rolling bed from its logged envelope
        self._mix_rolling_bed(output_data, total_samples)

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
