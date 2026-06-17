import wave
import struct
import math
import os
import numpy as np

SAMPLE_RATE = 44100


def _write_mono_wav(filepath, signal):
    """Writes a float32 [-1, 1] mono signal to a 16-bit PCM WAV file."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    pcm = (np.clip(signal, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(filepath, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm.tobytes())


def generate_impact_wav(filepath, modes, duration, noise_amount=0.5, noise_decay=600.0):
    """Generates a physically-inspired impact sound using modal synthesis.

    A real rigid-body collision is a sharp broadband contact transient (the
    "click") followed by the object's resonant modes ringing down. We model that
    as a short noise burst plus a sum of exponentially-decaying sinusoids.

    modes: list of (frequency_hz, decay_rate, amplitude). Higher decay_rate =
           more damped (thud); lower decay_rate = high-Q ring (glassy).
    """
    n = int(duration * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE

    signal = np.zeros(n, dtype=np.float32)

    # Resonant modes ringing down
    for freq, decay_rate, amp in modes:
        signal += amp * np.sin(2.0 * np.pi * freq * t) * np.exp(-decay_rate * t)

    # Contact transient: a very short broadband noise click at the moment of impact
    click_env = np.exp(-t * noise_decay)
    noise = (np.random.uniform(-1.0, 1.0, n) * click_env * noise_amount).astype(np.float32)
    signal += noise

    # A 1ms attack ramp prevents a hard DC step (which itself sounds like a click pop)
    attack = max(1, int(0.001 * SAMPLE_RATE))
    signal[:attack] *= np.linspace(0.0, 1.0, attack)

    # Normalize to a consistent peak level
    peak = np.max(np.abs(signal))
    if peak > 1e-9:
        signal = signal / peak * 0.9

    _write_mono_wav(filepath, signal)


def generate_rolling_wav(filepath, duration=1.0):
    """Generates a seamless, loopable low rumble used as the continuous rolling bed.

    All partials are placed on integer Hz (multiples of 1/duration) so the buffer is
    exactly periodic over `duration` seconds and loops without a seam click. A 1/f
    amplitude rolloff gives it a dark, surface-friction-like character.
    """
    n = int(duration * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    signal = np.zeros(n, dtype=np.float32)

    rng = np.random.RandomState(99)
    fundamental = 1.0 / duration  # integer-Hz spacing -> seamless loop
    for k in range(int(40 / fundamental), int(420 / fundamental), int(round(9 / fundamental))):
        freq = k * fundamental
        amp = 1.0 / (freq ** 0.9)
        phase = rng.uniform(0.0, 2.0 * np.pi)
        signal += amp * np.sin(2.0 * np.pi * freq * t + phase)

    peak = np.max(np.abs(signal))
    if peak > 1e-9:
        signal = signal / peak * 0.6

    _write_mono_wav(filepath, signal)


def generate_wav(filepath, frequency, duration, wave_type="sine", decay=True):
    """Generates a synthetic WAV sound effect using basic waveforms (used for
    non-physical event cues like the portal and finish sweeps)."""
    sample_rate = SAMPLE_RATE
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
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")

    # Use a fixed seed so regenerated assets are reproducible
    np.random.seed(1234)

    # 1. Marble-to-Marble: glassy high-pitched click that briefly rings (high-Q modes)
    generate_impact_wav(
        f"{base_dir}/marble_marble.wav",
        modes=[(2400, 16.0, 1.0), (3850, 24.0, 0.55), (5600, 34.0, 0.32)],
        duration=0.13, noise_amount=0.45, noise_decay=700.0,
    )

    # 2. Marble-to-Wall: dull, damped low thud (heavily damped low modes)
    generate_impact_wav(
        f"{base_dir}/marble_wall.wav",
        modes=[(280, 42.0, 1.0), (560, 58.0, 0.45), (980, 75.0, 0.22)],
        duration=0.18, noise_amount=0.6, noise_decay=450.0,
    )

    # 3. Marble-to-Box: mid woody clack (medium damping)
    generate_impact_wav(
        f"{base_dir}/marble_box.wav",
        modes=[(520, 30.0, 1.0), (900, 42.0, 0.5), (1500, 55.0, 0.28)],
        duration=0.15, noise_amount=0.55, noise_decay=550.0,
    )

    # 4. Teleportation Portal sound: sci-fi sweep up (non-physical cue)
    generate_wav(f"{base_dir}/portal.wav", (300, 1500), 0.25, wave_type="chirp", decay=True)

    # 5. Finish line sound: ascending celebratory sweep (non-physical cue)
    generate_wav(f"{base_dir}/finish.wav", (600, 1800), 0.35, wave_type="chirp", decay=True)

    # 6. Continuous rolling rumble bed (looped, volume-modulated by rolling activity)
    generate_rolling_wav(f"{base_dir}/rolling.wav", duration=1.0)

    print("Sound assets generated successfully!")


if __name__ == "__main__":
    build_sound_assets()
