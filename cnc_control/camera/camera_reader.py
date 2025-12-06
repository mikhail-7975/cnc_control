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
    def __init__(self, camera_id=4, calibration_file=None):
        """
        Initialize thread-safe camera reader.
        Undistortion (if any) is applied ONLY in get_image(), not in capture thread.

        Args:
            camera_id (int or str): Camera index or video path
            calibration_file (str or None): Path to .json/.npz for undistortion.
        """
        self.camera_id = camera_id
        self.undistorter = None
        if calibration_file is not None:
            self.undistorter = FisheyeUndistorter(calibration_file)

        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {camera_id}")
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        # Set resolution and FPS 4608x3456
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 8000)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 6000)
        self.cap.set(cv2.CAP_PROP_FPS, 5)
        
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"📹 Camera opened: {self.width}x{self.height}")

        # If undistorter is used, verify resolution matches
        if self.undistorter is not None:
            if (self.width, self.height) != self.undistorter.resolution:
                raise ValueError(
                    f"Camera resolution ({self.width}x{self.height}) does not match "
                    f"calibration resolution {self.undistorter.resolution}"
                )

        self._latest_raw_frame = np.zeros((6000, 8000, 3), dtype= "uint8")
        self._frame_lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _capture_loop(self):
        """Capture raw frames in background."""
        while self._running:
            with self._frame_lock:
                ret = self.cap.read(self._latest_raw_frame)
            if not ret:
                print("⚠️ Failed to read frame. Stopping capture.")
                time.sleep(0.05)
                continue
            


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
        #         # Optionally return raw frame or None — here we return raw
        #         # (you can change behavior as needed)
        return self._latest_raw_frame

    def stop(self):
        """Stop background thread and release camera."""
        self._running = False
        self._thread.join()
        self.cap.release()
        print("⏹️ Camera reader stopped.")

    def __del__(self):
        if hasattr(self, '_running') and self._running:
            self.stop()