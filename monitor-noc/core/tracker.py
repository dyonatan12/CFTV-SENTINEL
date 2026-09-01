from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from core.notifier import Notifier

class CameraStatus(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    PENDING_OFFLINE = "PENDING_OFFLINE"
    PENDING_ONLINE = "PENDING_ONLINE"

class DeviceState:
    def __init__(self, camera_data: dict, failure_threshold: int = 3, recovery_threshold: int = 2, get_client_fn: Optional[Callable] = None):
        self.camera = camera_data
        self.status = CameraStatus.ONLINE
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.failure_threshold = camera_data.get("custom_failure_threshold") or failure_threshold
        self.recovery_threshold = camera_data.get("custom_recovery_threshold") or recovery_threshold
        self.last_seen: datetime = datetime.now()
        self.last_latency_ms: float = 0.0
        self.last_snapshot_url: str = f"/snapshots/{camera_data.get('id')}.jpg"
        self.last_snapshot_time: str = ""
        self.last_snapshot_success: bool = False
        self.suppress_alert = False
        self.get_client_fn = get_client_fn

    def get_client_info(self) -> Optional[dict]:
        if self.get_client_fn:
            return self.get_client_fn(self.camera.get("client_id"))
        return None

    def update_result(self, is_success: bool, latency_ms: float = 0.0):
        self.last_latency_ms = latency_ms
        if is_success:
            self.last_seen = datetime.now()
            self.consecutive_failures = 0
            self.consecutive_successes += 1

            if self.status != CameraStatus.ONLINE:
                if self.consecutive_successes >= self.recovery_threshold:
                    self.status = CameraStatus.ONLINE
                    if not self.suppress_alert:
                        client_info = self.get_client_info()
                        Notifier.alert_camera_recovered(self.camera, client_info=client_info)
                else:
                    self.status = CameraStatus.PENDING_ONLINE
        else:
            self.consecutive_successes = 0
            self.consecutive_failures += 1

            if self.status != CameraStatus.OFFLINE:
                if self.consecutive_failures >= self.failure_threshold:
                    self.status = CameraStatus.OFFLINE
                    if not self.suppress_alert:
                        client_info = self.get_client_info()
                        Notifier.alert_camera_down(self.camera, self.consecutive_failures, client_info=client_info)
                else:
                    self.status = CameraStatus.PENDING_OFFLINE

class NvrGroupState:
    def __init__(self, nvr_name: str, dvr_ip: str, client_id: str = None, get_client_fn: Optional[Callable] = None):
        self.nvr_name = nvr_name
        self.dvr_ip = dvr_ip
        self.client_id = client_id
        self.get_client_fn = get_client_fn
        self.is_offline = False
        self.devices: List[DeviceState] = []

    def get_client_info(self) -> Optional[dict]:
        if self.get_client_fn and self.client_id:
            return self.get_client_fn(self.client_id)
        return None

    def check_nvr_health(self):
        if len(self.devices) <= 1:
            return

        total = len(self.devices)
        offline_count = sum(1 for d in self.devices if d.status == CameraStatus.OFFLINE)
        
        is_nvr_down = (offline_count >= 2 and offline_count >= (total * 0.5))

        if is_nvr_down and not self.is_offline:
            self.is_offline = True
            for d in self.devices:
                d.suppress_alert = True
            client_info = self.get_client_info()
            Notifier.alert_nvr_down(self.nvr_name, self.dvr_ip, total, offline_count, client_info=client_info)

        elif not is_nvr_down and self.is_offline:
            if offline_count == 0 or (total - offline_count) >= (total * 0.8):
                self.is_offline = False
                for d in self.devices:
                    d.suppress_alert = False
                client_info = self.get_client_info()
                Notifier.alert_nvr_recovered(self.nvr_name, self.dvr_ip, total, client_info=client_info)

class DeviceTracker:
    def __init__(self, cameras: list[dict], failure_threshold: int = 3, recovery_threshold: int = 2, get_client_fn: Optional[Callable] = None):
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.get_client_fn = get_client_fn
        self.devices: Dict[str, DeviceState] = {}
        self.nvrs: Dict[str, NvrGroupState] = {}
        
        for cam in cameras:
            self.add_or_update_device(cam)

    def get_device(self, cam_id: str) -> DeviceState:
        return self.devices.get(cam_id)

    def add_or_update_device(self, camera_data: dict):
        cam_id = camera_data["id"]
        dev_state = DeviceState(camera_data, self.failure_threshold, self.recovery_threshold, self.get_client_fn)
        self.devices[cam_id] = dev_state
        
        nvr_name = camera_data.get("nvr") or "N/A"
        client_id = camera_data.get("client_id")
        
        if nvr_name and nvr_name != "N/A":
            nvr_key = f"{client_id or 'default'}_{nvr_name}"
            if nvr_key not in self.nvrs:
                self.nvrs[nvr_key] = NvrGroupState(nvr_name, camera_data.get("ip", ""), client_id, self.get_client_fn)
            if dev_state not in self.nvrs[nvr_key].devices:
                self.nvrs[nvr_key].devices.append(dev_state)

    def remove_device(self, cam_id: str):
        if cam_id in self.devices:
            dev = self.devices[cam_id]
            nvr_name = dev.camera.get("nvr")
            client_id = dev.camera.get("client_id")
            nvr_key = f"{client_id or 'default'}_{nvr_name}"
            if nvr_key in self.nvrs and dev in self.nvrs[nvr_key].devices:
                self.nvrs[nvr_key].devices.remove(dev)
            del self.devices[cam_id]

    def evaluate_nvrs(self):
        for nvr in self.nvrs.values():
            nvr.check_nvr_health()

    def get_summary(self, client_id_filter: str = None) -> dict:
        target_devs = self.devices.values()
        if client_id_filter and client_id_filter != "all":
            target_devs = [d for d in target_devs if d.camera.get("client_id") == client_id_filter]

        total = len(target_devs)
        online = sum(1 for d in target_devs if d.status == CameraStatus.ONLINE)
        offline = sum(1 for d in target_devs if d.status == CameraStatus.OFFLINE)
        pending = total - online - offline
        return {
            "total": total,
            "online": online,
            "offline": offline,
            "pending": pending
        }
