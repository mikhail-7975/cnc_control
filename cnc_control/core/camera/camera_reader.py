import threading
import time
import cv2
import numpy as np
from pathlib import Path
import json

# -----------------------------
# FisheyeUndistorter (unchanged)
# -----------------------------
class FisheyeUndistorter:
    def __init__(self, calibration_file):
        self.K = None
        self.D = None
        self.resolution = None
        
        calibration_path = Path(calibration_file)
        
        if calibration_path.suffix == '.json':
            self._load_json(calibration_path)
        elif calibration_path.suffix == '.npz':
            self._load_npz(calibration_path)
        else:
            raise ValueError("Calibration file must be .json or .npz")
        
        self.map1, self.map2 = cv2.fisheye.initUndistortRectifyMap(
            self.K, self.D,
            np.eye(3),
            self.K,
            self.resolution,
            cv2.CV_16SC2
        )
        print(f"✅ Loaded calibration: {calibration_file}")
        print(f"   Resolution: {self.resolution[0]}x{self.resolution[1]}")
        print(f"   RMS error: {getattr(self, 'rms_error', 'N/A')}")

    def _load_json(self, path):
        with open(path, 'r') as f:
            data = json.load(f)
        self.K = np.array(data["camera_matrix"], dtype=np.float32)
        self.D = np.array(data["distortion_coefficients"], dtype=np.float32).reshape(-1, 1)
        self.resolution = (data["resolution"]["width"], data["resolution"]["height"])
        self.rms_error = data.get("rms_error", "N/A")

    def _load_npz(self, path):
        data = np.load(path)
        self.K = data["camera_matrix"].astype(np.float32)
        self.D = data["distortion_coefficients"].astype(np.float32).reshape(-1, 1)
        self.resolution = tuple(data["resolution"])
        self.rms_error = float(data.get("rms_error", "N/A"))

    def undistort(self, frame):
        if frame.shape[1] != self.resolution[0] or frame.shape[0] != self.resolution[1]:
            raise ValueError(
                f"Frame resolution {frame.shape[1]}x{frame.shape[0]} "
                f"doesn't match calibration {self.resolution[0]}x{self.resolution[1]}"
            )
        return cv2.remap(frame, self.map1, self.map2, interpolation=cv2.INTER_LINEAR)


# -----------------------------
# Thread-Safe Camera Reader (undistort in get_image)
# -----------------------------
class ThreadSafeCameraReader:
    def __init__(self, camera_id=4, calibration_file=None, backend=None, res_mode = '1080', photo_mode = 'etalon'):
        """
        Initialize thread-safe camera reader.
        Undistortion (if any) is applied ONLY in get_image(), not in capture thread.

        Args:
            camera_id (int or str): Camera index or video path
            calibration_file (str or None): Path to .json/.npz for undistortion.
            backend: cv2.CAP_DSHOW or cv2.CAP_MSMF (None for auto)
        """
        self.camera_id = camera_id
        self.undistorter = None
        if calibration_file is not None:
            self.undistorter = FisheyeUndistorter(calibration_file)

        # Try to use DirectShow backend on Windows (more stable than MSMF)
        if backend is None:
            try:
                # Try DirectShow first (more stable on Windows)
                self.cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
                if not self.cap.isOpened():
                    # Fallback to MSMF
                    self.cap = cv2.VideoCapture(camera_id, cv2.CAP_MSMF)
            except (AttributeError, ValueError):
                # Fallback to default backend if constants are not available
                self.cap = cv2.VideoCapture(camera_id)
        else:
            self.cap = cv2.VideoCapture(camera_id, backend)
            
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {camera_id}")
        
        # Set buffer size to reduce latency (helps with MSMF issues)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Set codec
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        self.photo_mode = photo_mode
        # Set resolution and FPS
        if res_mode == '1080':
            preferred_width = 1920
            preferred_height = 1080
            preferred_fps = 30

        else:
            preferred_width = 8000
            preferred_height = 6000
            preferred_fps = 5
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, preferred_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, preferred_height)
        self.cap.set(cv2.CAP_PROP_FPS, preferred_fps)
        
        # Allow camera to apply settings
        time.sleep(0.2)
        
        # Read a few frames to initialize (discard them)
        # This is especially important for high resolution cameras
        for _ in range(5):
            ret, _ = self.cap.read()
            if not ret:
                break
            time.sleep(0.1)  # Give camera more time for high-res frames
        
        # Get actual resolution from camera (may differ from requested)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        print(f"📹 Camera opened: {self.width}x{self.height} @ {actual_fps:.1f} FPS")
        if self.width != preferred_width or self.height != preferred_height:
            print(f"⚠️  Requested {preferred_width}x{preferred_height}, got {self.width}x{self.height}")
        if actual_fps != preferred_fps:
            print(f"⚠️  Requested {preferred_fps} FPS, got {actual_fps:.1f} FPS")

        # If undistorter is used, verify resolution matches
        if self.undistorter is not None:
            if (self.width, self.height) != self.undistorter.resolution:
                raise ValueError(
                    f"Camera resolution ({self.width}x{self.height}) does not match "
                    f"calibration resolution {self.undistorter.resolution}"
                )

        self._latest_raw_frame = None
        self._frame_lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        
        # Wait a bit for first frame to be captured
        time.sleep(0.2)

    def _capture_loop(self):
        """Capture raw frames in background."""
        consecutive_failures = 0
        max_failures = 10
        
        while self._running:
            # Don't pass buffer to read() - let it allocate its own frame
            ret, frame = self.cap.read()
            
            if not ret:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    print(f"⚠️ Failed to read frame {consecutive_failures} times. Camera may be disconnected.")
                    time.sleep(0.1)
                else:
                    time.sleep(0.01)
                continue
            
            # Reset failure counter on success
            consecutive_failures = 0
            
            # Store frame with lock protection
            with self._frame_lock:
                self._latest_raw_frame = frame

            time.sleep(0.001)  # optional: reduce CPU

    def get_image(self):
        """
        Get the latest frame, applying undistortion if enabled.

        Returns:
            np.ndarray or None: Undistorted (or raw) image, or None if not ready.
        """
        # with self._frame_lock:
        #     if self._latest_raw_frame is None:
        #         return None
        #     frame = self._latest_raw_frame.copy()

        # # Apply undistortion OUTSIDE the lock (to avoid holding lock during processing)
        # if self.undistorter is not None:
        #     try:
        #         frame = self.undistorter.undistort(frame)
        #     except Exception as e:
        #         print(f"❌ Undistortion failed in get_image(): {e}")
        #         # Return raw frame if undistortion fails
        h, w, _ = self._latest_raw_frame.shape
        if self.photo_mode == 'etalon':
            return self._latest_raw_frame[h//2-500:h//2+500, w//2-500:w//2+500]
        else:
            return self._latest_raw_frame[500:5500, 1500:6500]

    def stop(self):
        """Stop background thread and release camera."""
        self._running = False
        self._thread.join()
        self.cap.release()
        print("⏹️ Camera reader stopped.")

    def __del__(self):
        if hasattr(self, '_running') and self._running:
            self.stop()