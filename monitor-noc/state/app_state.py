import os
import json
import time
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from config import CONFIG
from core.tracker import DeviceTracker
from core.checker import check_camera_health
from core.snapshot import capture_snapshot
from core.event_bus import EVENT_BUS
from core.database import DB

logger = logging.getLogger("cftv.state")

class AppState:
    def __init__(self):
        self.is_mock: bool = False
        self.clients_file: str = CONFIG.clients_file
        self.cameras_file: str = CONFIG.cameras_file
        self.clients: List[dict] = []
        self.cameras: List[dict] = []
        self.tracker: Optional[DeviceTracker] = None
        self.cycle: int = 0
        self.last_scan_time: str = "Nunca"
        self.last_scan_duration_ms: float = 0.0
        self.event_subscribers: List[asyncio.Queue] = []
        self.is_scanning: bool = False

        # Registra listeners no EventBus
        EVENT_BUS.subscribe("CAMERA_DOWN", self._on_camera_down_event)
        EVENT_BUS.subscribe("CAMERA_RECOVERED", self._on_camera_recovered_event)
        EVENT_BUS.subscribe("NVR_DOWN", self._on_nvr_down_event)
        EVENT_BUS.subscribe("NVR_RECOVERED", self._on_nvr_recovered_event)

    def get_client_by_id(self, client_id: str) -> Optional[dict]:
        if not client_id:
            return None
        return next((c for c in self.clients if c.get("id") == client_id), None)

    def load_clients(self, clients_path: Optional[str] = None):
        path = clients_path or self.clients_file
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.clients = json.load(f)
            except Exception as e:
                logger.error(f"Erro ao carregar clientes ({path}): {e}")
                self.clients = []
        else:
            self.clients = []

    def save_clients(self):
        try:
            with open(self.clients_file, "w", encoding="utf-8") as f:
                json.dump(self.clients, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar clientes: {e}")

    def load_cameras(self, cameras_path: Optional[str] = None):
        path = cameras_path or self.cameras_file
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.cameras = json.load(f)
            except Exception as e:
                logger.error(f"Erro ao carregar câmeras ({path}): {e}")
                self.cameras = []
        else:
            self.cameras = []

        self.tracker = DeviceTracker(
            self.cameras,
            failure_threshold=CONFIG.failure_threshold,
            recovery_threshold=CONFIG.recovery_threshold,
            get_client_fn=self.get_client_by_id
        )

    def ensure_tracker_initialized(self):
        if self.tracker is None:
            self.tracker = DeviceTracker(
                self.cameras,
                failure_threshold=CONFIG.failure_threshold,
                recovery_threshold=CONFIG.recovery_threshold,
                get_client_fn=self.get_client_by_id
            )

    def save_cameras(self):
        try:
            with open(self.cameras_file, "w", encoding="utf-8") as f:
                json.dump(self.cameras, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar câmeras: {e}")

    async def broadcast_sse(self, event_type: str, data: dict):
        payload = json.dumps({"type": event_type, "data": data, "timestamp": datetime.now().isoformat()})
        for dq in list(self.event_subscribers):
            try:
                await dq.put(payload)
            except Exception:
                if dq in self.event_subscribers:
                    self.event_subscribers.remove(dq)

    async def trigger_camera_snapshot(self, cam_dict: dict):
        self.ensure_tracker_initialized()
        dev = self.tracker.get_device(cam_dict["id"]) if self.tracker else None
        success, result_url = await capture_snapshot(cam_dict, is_mock=self.is_mock)
        if dev:
            dev.last_snapshot_success = success
            if success:
                dev.last_snapshot_url = result_url
                dev.last_snapshot_time = datetime.now().strftime("%H:%M:%S")

    async def perform_scan(self):
        self.ensure_tracker_initialized()
        if self.is_scanning or not self.tracker:
            return
        self.is_scanning = True

        start_time = time.perf_counter()
        sem = asyncio.Semaphore(CONFIG.max_concurrent_checks)
        timeout = CONFIG.connection_timeout

        async def check_single(dev_data):
            async with sem:
                cam_id = dev_data["id"]
                custom_timeout = dev_data.get("custom_timeout") or timeout
                is_ok, latency = await check_camera_health(
                    camera_data=dev_data,
                    timeout=custom_timeout,
                    is_mock=self.is_mock
                )
                return cam_id, is_ok, latency

        tasks = [check_single(c) for c in list(self.cameras)]
        if tasks:
            results = await asyncio.gather(*tasks)
            for cam_id, is_success, latency in results:
                dev = self.tracker.get_device(cam_id)
                if dev:
                    dev.update_result(is_success, latency)
                    if is_success:
                        dev.last_snapshot_success = True
                        dev.last_snapshot_url = f"/snapshots/{cam_id}.jpg"
                        dev.last_snapshot_time = datetime.now().strftime("%H:%M:%S")

            self.tracker.evaluate_nvrs()

        self.cycle += 1
        self.last_scan_duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
        self.last_scan_time = datetime.now().strftime("%H:%M:%S")
        self.is_scanning = False

        await self.broadcast_sse("STATUS_UPDATE", {})

    async def background_monitoring_loop(self):
        await asyncio.sleep(1)
        for cam in self.cameras:
            asyncio.create_task(self.trigger_camera_snapshot(cam))

        while True:
            try:
                await self.perform_scan()
            except Exception as e:
                logger.error(f"Erro no monitor loop: {e}")

            interval = max(CONFIG.check_interval, 5)
            await asyncio.sleep(interval)

    # Event Handlers do EventBus + Persistência em Banco
    def _on_camera_down_event(self, camera: dict, failures: int, client_info: dict, text: str):
        client_name = (client_info.get("name") if client_info else None) or camera.get("client_name") or "Geral"
        client_id = camera.get("client_id", "default")
        
        # Grava no banco SQLite
        DB.log_alert(
            device_id=camera["id"],
            device_name=camera.get("name", "Câmera"),
            status="OFFLINE",
            event_type="CAMERA_DOWN",
            client_id=client_id,
            client_name=client_name,
            failures=failures,
            channel=str(camera.get("channel", 1)),
            message=text
        )

        asyncio.create_task(self.broadcast_sse("ALERT", {
            "id": camera["id"],
            "name": camera["name"],
            "client_name": client_name,
            "ip": camera["ip"],
            "status": "OFFLINE",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "failures": failures
        }))

    def _on_camera_recovered_event(self, camera: dict, client_info: dict, text: str):
        client_name = (client_info.get("name") if client_info else None) or camera.get("client_name") or "Geral"
        client_id = camera.get("client_id", "default")

        # Grava no banco SQLite
        DB.log_alert(
            device_id=camera["id"],
            device_name=camera.get("name", "Câmera"),
            status="ONLINE",
            event_type="CAMERA_RECOVERED",
            client_id=client_id,
            client_name=client_name,
            failures=0,
            channel=str(camera.get("channel", 1)),
            message=text
        )

        asyncio.create_task(self.broadcast_sse("ALERT", {
            "id": camera["id"],
            "name": camera["name"],
            "client_name": client_name,
            "ip": camera["ip"],
            "status": "ONLINE",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }))

    def _on_nvr_down_event(self, nvr_name: str, dvr_ip: str, total_channels: int, offline_count: int, client_info: dict, text: str):
        client_name = (client_info.get("name") if client_info else None) or "Geral"
        client_id = (client_info.get("id") if client_info else None) or "default"

        DB.log_alert(
            device_id=f"nvr-{nvr_name}",
            device_name=f"GRAVADOR {nvr_name}",
            status="OFFLINE",
            event_type="NVR_DOWN",
            client_id=client_id,
            client_name=client_name,
            failures=offline_count,
            channel=f"{offline_count}/{total_channels}",
            message=text
        )

        asyncio.create_task(self.broadcast_sse("ALERT", {
            "id": f"nvr-{nvr_name}",
            "name": f"GRAVADOR {nvr_name}",
            "client_name": client_name,
            "ip": dvr_ip,
            "status": "OFFLINE",
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "failures": f"{offline_count}/{total_channels} canais"
        }))

    def _on_nvr_recovered_event(self, nvr_name: str, dvr_ip: str, total_channels: int, client_info: dict, text: str):
        client_name = (client_info.get("name") if client_info else None) or "Geral"
        client_id = (client_info.get("id") if client_info else None) or "default"

        DB.log_alert(
            device_id=f"nvr-{nvr_name}",
            device_name=f"GRAVADOR {nvr_name}",
            status="ONLINE",
            event_type="NVR_RECOVERED",
            client_id=client_id,
            client_name=client_name,
            failures=0,
            channel=f"{total_channels}/{total_channels}",
            message=text
        )

        asyncio.create_task(self.broadcast_sse("ALERT", {
            "id": f"nvr-{nvr_name}",
            "name": f"GRAVADOR {nvr_name}",
            "client_name": client_name,
            "ip": dvr_ip,
            "status": "ONLINE",
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }))

GLOBAL_STATE = AppState()
GLOBAL_STATE.load_clients()
GLOBAL_STATE.load_cameras()
