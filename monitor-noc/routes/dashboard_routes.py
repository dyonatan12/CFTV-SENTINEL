import os
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, Response

from core.tracker import CameraStatus
from core.snapshot import get_rtsp_url, SNAPSHOT_DIR
from core.security import sanitize_device_for_api
from state.app_state import GLOBAL_STATE

router = APIRouter(tags=["Dashboard"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@router.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    template_path = os.path.join(BASE_DIR, "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@router.get("/app", response_class=HTMLResponse)
async def serve_client_app():
    template_path = os.path.join(BASE_DIR, "templates", "client_app.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@router.get("/ios", response_class=HTMLResponse)
async def serve_ios_preview():
    template_path = os.path.join(BASE_DIR, "templates", "ios_preview.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@router.get("/architecture", response_class=HTMLResponse)
async def serve_architecture():
    arch_path = os.path.join(os.path.dirname(BASE_DIR), "cftv-sentinel-architecture.html")
    if not os.path.exists(arch_path):
        arch_path = os.path.join(BASE_DIR, "cftv-sentinel-architecture.html")
    if os.path.exists(arch_path):
        with open(arch_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h1>Mapa de arquitetura não encontrado.</h1>", status_code=404)

@router.get("/snapshots/{filename}")
async def get_snapshot_image(filename: str):
    file_path = os.path.join(SNAPSHOT_DIR, filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            return Response(content=content, media_type="image/jpeg", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
        except Exception:
            pass

    default_path = os.path.join(SNAPSHOT_DIR, "default.jpg")
    if os.path.exists(default_path):
        try:
            with open(default_path, "rb") as f:
                content = f.read()
            return Response(content=content, media_type="image/jpeg", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
        except Exception:
            pass

    return Response(status_code=404)

@router.get("/api/status")
async def get_status(client_id: Optional[str] = None):
    GLOBAL_STATE.ensure_tracker_initialized()
    if not GLOBAL_STATE.tracker:
        return JSONResponse({"error": "Inicializando..."}, status_code=503)

    summary = GLOBAL_STATE.tracker.get_summary(client_id_filter=client_id)
    devices_list = []
    
    for cam in GLOBAL_STATE.cameras:
        if client_id and client_id != "all" and cam.get("client_id") != client_id:
            continue

        dev_state = GLOBAL_STATE.tracker.get_device(cam["id"])
        if dev_state:
            client_obj = GLOBAL_STATE.get_client_by_id(cam.get("client_id"))
            client_name = client_obj.get("name") if client_obj else "Geral"

            dev_payload = {
                "id": cam["id"],
                "name": cam["name"],
                "ip": cam["ip"],
                "port": cam.get("port", 554),
                "http_port": cam.get("http_port", 80),
                "nvr": cam.get("nvr", "N/A"),
                "channel": cam.get("channel", 0),
                "client_id": cam.get("client_id", "default"),
                "client_name": client_name,
                "username": cam.get("username", "admin"),
                "password": cam.get("password", ""),
                "status": dev_state.status.value,
                "latency_ms": round(dev_state.last_latency_ms, 1),
                "failures": dev_state.consecutive_failures,
                "last_seen": dev_state.last_seen.strftime("%H:%M:%S"),
                "snapshot_url": dev_state.last_snapshot_url,
                "snapshot_time": dev_state.last_snapshot_time or dev_state.last_seen.strftime("%H:%M:%S"),
                "snapshot_success": dev_state.last_snapshot_success,
                "rtsp_url": get_rtsp_url(cam)
            }
            devices_list.append(sanitize_device_for_api(dev_payload))

    return {
        "summary": summary,
        "clients": GLOBAL_STATE.clients,
        "cycle": GLOBAL_STATE.cycle,
        "last_scan": GLOBAL_STATE.last_scan_time,
        "scan_time_ms": GLOBAL_STATE.last_scan_duration_ms,
        "is_mock": GLOBAL_STATE.is_mock,
        "devices": devices_list
    }
