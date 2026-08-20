import threading
import time
import cv2
import numpy as np

try:
    import pyvirtualcam
    PYVIRTUALCAM_AVAILABLE = True
except ImportError:
    PYVIRTUALCAM_AVAILABLE = False


class VirtualCamManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.cam = None
        self.is_active = False
        self.width = 640
        self.height = 480
        self.fps = 25
        self.last_error = None
        self.current_backend = None
        self._frame_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = VirtualCamManager()
            return cls._instance

    def check_availability(self) -> dict:
        """Check if pyvirtualcam and a virtual camera device are available."""
        if not PYVIRTUALCAM_AVAILABLE:
            return {
                "available": False,
                "active": self.is_active,
                "backend": None,
                "error": "pyvirtualcam library not installed"
            }

        if self.is_active and self.cam is not None:
            return {
                "available": True,
                "active": True,
                "backend": self.current_backend,
                "device": getattr(self.cam, "device", "Virtual Camera"),
                "width": self.width,
                "height": self.height,
                "error": None
            }

        # Test if a virtual device can be initialized
        try:
            test_cam = pyvirtualcam.Camera(width=320, height=240, fps=20, print_fps=False)
            device_name = getattr(test_cam, "device", "Virtual Camera")
            test_cam.close()
            return {
                "available": True,
                "active": False,
                "backend": "native",
                "device": device_name,
                "error": None
            }
        except Exception as e:
            return {
                "available": False,
                "active": False,
                "backend": None,
                "error": str(e)
            }

    def start(self, width: int = 640, height: int = 480, fps: int = 25) -> dict:
        """Start streaming to the virtual camera device."""
        if not PYVIRTUALCAM_AVAILABLE:
            raise RuntimeError("pyvirtualcam is not installed.")

        with self._frame_lock:
            if self.is_active and self.cam is not None:
                # If already active with same dimensions, return
                if self.width == width and self.height == height:
                    return {"status": "already_running", "device": getattr(self.cam, "device", "Virtual Camera")}
                self.stop()

            try:
                # pyvirtualcam natively expects RGB by default or fmt=pyvirtualcam.PixelFormat.BGR
                self.cam = pyvirtualcam.Camera(
                    width=width,
                    height=height,
                    fps=fps,
                    fmt=pyvirtualcam.PixelFormat.BGR,
                    print_fps=False
                )
                self.width = width
                self.height = height
                self.fps = fps
                self.is_active = True
                self.last_error = None
                self.current_backend = getattr(self.cam, "device", "Virtual Camera")
                print(f"[VirtualCam] Started Virtual Camera: {self.current_backend} ({width}x{height} @ {fps}fps)")
                return {
                    "status": "started",
                    "device": self.current_backend,
                    "width": width,
                    "height": height,
                    "fps": fps
                }
            except Exception as e:
                self.is_active = False
                self.cam = None
                self.last_error = str(e)
                print(f"[VirtualCam] Failed to start Virtual Camera: {e}")
                raise RuntimeError(f"Could not start virtual camera: {e}")

    def push_frame(self, frame_bgr: np.ndarray):
        """Send a single BGR frame to the virtual camera."""
        if not self.is_active or self.cam is None:
            return

        with self._frame_lock:
            if not self.is_active or self.cam is None:
                return
            try:
                # Ensure frame matches target size
                h, w = frame_bgr.shape[:2]
                if w != self.width or h != self.height:
                    frame_bgr = cv2.resize(frame_bgr, (self.width, self.height), interpolation=cv2.INTER_LINEAR)

                # Send frame to virtual camera
                self.cam.send(frame_bgr)
            except Exception as e:
                print(f"[VirtualCam] Frame send error: {e}")

    def stop(self):
        """Stop and release the virtual camera."""
        with self._frame_lock:
            if self.cam is not None:
                try:
                    self.cam.close()
                    print("[VirtualCam] Closed Virtual Camera device.")
                except Exception as e:
                    print(f"[VirtualCam] Error closing virtual camera: {e}")
                finally:
                    self.cam = None
            self.is_active = False
            self.current_backend = None
        return {"status": "stopped"}
