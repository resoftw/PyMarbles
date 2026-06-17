import cv2
import numpy as np
import pygame
import os

class VideoExporter:
    def __init__(self):
        self.writer = None
        self.filename = None
        self.width = None
        self.height = None
        self.fps = None
        self.recording = False

    def start_recording(self, filename, width, height, fps=60):
        """Starts recording. Opens the OpenCV VideoWriter."""
        if self.recording:
            return False
            
        self.filename = filename
        self.width = width
        self.height = height
        self.fps = fps
        
        # Ensure output folder exists
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        # Try H264 codec first, fallback to mp4v if H264 is not available
        try:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v') # Universal MP4 codec
            self.writer = cv2.VideoWriter(filename, fourcc, fps, (width, height))
            if not self.writer.isOpened():
                raise RuntimeError("Failed to open video writer with mp4v")
        except Exception as e:
            print(f"Error starting video recorder: {e}")
            self.writer = None
            self.recording = False
            return False
            
        self.recording = True
        return True

    def write_frame(self, pygame_surface):
        """Captures a frame from a Pygame surface and writes it to the MP4 file."""
        if not self.recording or self.writer is None:
            return False
            
        try:
            # Capture the raw RGB pixel data from pygame surface
            try:
                raw_data = pygame.image.tobytes(pygame_surface, 'RGB')
            except AttributeError:
                # Compatibility fallback for older pygame versions
                raw_data = pygame.image.tostring(pygame_surface, 'RGB')
                
            # Convert raw RGB string/buffer to numpy array
            frame = np.frombuffer(raw_data, dtype=np.uint8)
            frame = frame.reshape((self.height, self.width, 3))
            
            # OpenCV expects BGR format
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Write to video file
            self.writer.write(frame_bgr)
            return True
        except Exception as e:
            print(f"Error writing video frame: {e}")
            return False

    def stop_recording(self):
        """Finalizes the video export and releases the writer."""
        if not self.recording:
            return False
            
        if self.writer is not None:
            self.writer.release()
            self.writer = None
            
        self.recording = False
        print(f"Video saved successfully to: {self.filename}")
        return True
