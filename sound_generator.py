import wave
import struct
import math
import os

def generate_wav(filepath, frequency, duration, wave_type="sine", decay=True):
    """Generates a synthetic WAV sound effect using basic waveforms."""
    sample_rate = 44100
    num_samples = int(duration * sample_rate)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    
    with wave.open(filepath, 'wb') as wav_file:
        # Mono, 2 bytes per sample, 44100 sample rate
        wav_file.setparams((1, 2, sample_rate, num_samples, 'NONE', 'not compressed'))
        
        for i in range(num_samples):
            t = float(i) / sample_rate
            
            # Decay envelope: fades out towards the end
            if decay:
                envelope = math.exp(-t * (6.0 / duration))
            else:
                envelope = 1.0
                
            if wave_type == "sine":
                value = math.sin(2.0 * math.pi * frequency * t)
            elif wave_type == "chirp":
                # frequency is a tuple of (start_freq, end_freq)
                f_start, f_end = frequency
                current_freq = f_start + (f_end - f_start) * (t / duration)
                value = math.sin(2.0 * math.pi * current_freq * t)
            elif wave_type == "noise":
                # Create noise with a filter (rough clicking sound)
                import random
                value = random.uniform(-1.0, 1.0)
                # low pass filter approximation
                value = value * 0.4 + math.sin(2.0 * math.pi * 300 * t) * 0.6
            else:
                value = math.sin(2.0 * math.pi * frequency * t)
                
            # Clamp value to prevent distortion
            value = max(-1.0, min(1.0, value))
            
            # Convert to 16-bit signed integer
            int_val = int(value * envelope * 32767)
            packed_value = struct.pack('<h', int_val)
            wav_file.writeframes(packed_value)

def build_sound_assets():
    """Generates all standard sound assets needed for the game."""
    base_dir = "D:/Projects/2026/Python/Marbles/sounds"
    
    # 1. Marble-to-Marble: short high click
    generate_wav(f"{base_dir}/marble_marble.wav", 1200, 0.06, wave_type="sine", decay=True)
    
    # 2. Marble-to-Wall: dull low thud
    generate_wav(f"{base_dir}/marble_wall.wav", 220, 0.12, wave_type="sine", decay=True)
    
    # 3. Marble-to-Box: slightly higher box wood clack
    generate_wav(f"{base_dir}/marble_box.wav", 480, 0.08, wave_type="sine", decay=True)
    
    # 4. Teleportation Portal sound: sci-fi sweep up
    generate_wav(f"{base_dir}/portal.wav", (300, 1500), 0.25, wave_type="chirp", decay=True)
    
    # 5. Finish line sound: ascending celebratory chord
    generate_wav(f"{base_dir}/finish.wav", (600, 1800), 0.35, wave_type="chirp", decay=True)
    
    print("Sound assets generated successfully!")

if __name__ == "__main__":
    build_sound_assets()
