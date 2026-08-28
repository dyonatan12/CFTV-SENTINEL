from enum import Enum
from typing import Dict, Any, List
from datetime import datetime
from notifier import Notifier

class CameraStatus(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    PENDING_OFFLINE = "PENDING_OFFLINE"
    PENDING_ONLINE = "PENDING_ONLINE"

class DeviceState:
    def __init__(self, camera_data: dict, failure_threshold: int = 3, recovery_threshold: int = 2):
        self.camera = camera_data
        self.status = CameraStatus.ONLINE
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.last_seen: datetime = datetime.now()
        self.last_latency_ms: float = 0.0
        self.last_snapshot_url: str = f"/snapshots/{camera_data.get('id')}.jpg"
        self.last_snapshot_time: str = ""
        self.last_snapshot_success: bool = False
        self.suppress_alert = False # Se o NVR inteiro caiu, suprime alerta individual

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
                        Notifier.alert_camera_recovered(self.camera)
                else:
                    self.status = CameraStatus.PENDING_ONLINE
        else:
            self.consecutive_successes = 0
            self.consecutive_failures += 1

            if self.status != CameraStatus.OFFLINE:
                if self.consecutive_failures >= self.failure_threshold:
                    self.status = CameraStatus.OFFLINE
                    if not self.suppress_alert:
                        Notifier.alert_camera_down(self.camera, self.consecutive_failures)
                else:
                    self.status = CameraStatus.PENDING_OFFLINE

class NvrGroupState:
    def __init__(self, nvr_name: str, dvr_ip: str):
        self.nvr_name = nvr_name
        self.dvr_ip = dvr_ip
        self.is_offline = False
        self.devices: List[DeviceState] = []

    def check_nvr_health(self):
        """Avalia se o gravador como um todo caiu ou voltou"""
        if len(self.devices) <= 1:
            # Gravador com 1 única câmera ou câmera avulsa: não precisa de agrupamento
            return

        total = len(self.devices)
        offline_count = sum(1 for d in self.devices if d.status == CameraStatus.OFFLINE)
        
        # Se mais de 50% dos canais (e pelo menos 2) caírem juntos -> Queda de DVR inteiro
        is_nvr_down = (offline_count >= 2 and offline_count >= (total * 0.5))

        if is_nvr_down and not self.is_offline:
            self.is_offline = True
            # Suprime alertas individuais dos canais para evitar flood
            for d in self.devices:
                d.suppress_alert = True
            Notifier.alert_nvr_down(self.nvr_name, self.dvr_ip, total, offline_count)

        elif not is_nvr_down and self.is_offline:
            # Quando a maioria dos canais voltar
            if offline_count == 0 or (total - offline_count) >= (total * 0.8):
                self.is_offline = False
                for d in self.devices:
                    d.suppress_alert = False
                Notifier.alert_nvr_recovered(self.nvr_name, self.dvr_ip, total)

class DeviceTracker:
    def __init__(self, cameras: list[dict], failure_threshold: int = 3, recovery_threshold: int = 2):
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.devices: Dict[str, DeviceState] = {}
        self.nvrs: Dict[str, NvrGroupState] = {}
        
        for cam in cameras:
            self.add_or_update_device(cam)

    def get_device(self, cam_id: str) -> DeviceState:
        return self.devices.get(cam_id)

    def add_or_update_device(self, camera_data: dict):
        cam_id = camera_data["id"]
        dev_state = DeviceState(camera_data, self.failure_threshold, self.recovery_threshold)
        self.devices[cam_id] = dev_state
        
        nvr_name = camera_data.get("nvr") or "N/A"
        if nvr_name and nvr_name != "N/A":
            if nvr_name not in self.nvrs:
                self.nvrs[nvr_name] = NvrGroupState(nvr_name, camera_data.get("ip", ""))
            if dev_state not in self.nvrs[nvr_name].devices:
                self.nvrs[nvr_name].devices.append(dev_state)

    def remove_device(self, cam_id: str):
        if cam_id in self.devices:
            dev = self.devices[cam_id]
            nvr_name = dev.camera.get("nvr")
            if nvr_name in self.nvrs and dev in self.nvrs[nvr_name].devices:
                self.nvrs[nvr_name].devices.remove(dev)
            del self.devices[cam_id]

    def evaluate_nvrs(self):
        """Avalia a saúde coletiva de todos os gravadores após o ciclo de varredura"""
        for nvr in self.nvrs.values():
            nvr.check_nvr_health()

    def get_summary(self) -> dict:
        total = len(self.devices)
        online = sum(1 for d in self.devices.values() if d.status == CameraStatus.ONLINE)
        offline = sum(1 for d in self.devices.values() if d.status == CameraStatus.OFFLINE)
        pending = total - online - offline
        return {
            "total": total,
            "online": online,
            "offline": offline,
            "pending": pending
        }
