import os
import sys
import json
import uuid
import time
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import CONFIG
from checker import check_camera_health, mock_check_camera
from tracker import DeviceTracker, CameraStatus
from notifier import Notifier
from snapshot import capture_snapshot, get_rtsp_url, SNAPSHOT_DIR

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Carrega clientes, câmeras e inicia background loop
    load_clients_into_state(CONFIG.clients_file)
    load_cameras_into_state(CONFIG.cameras_file)
    task = asyncio.create_task(background_monitoring_loop())
    yield
    # Shutdown
    task.cancel()

app = FastAPI(title="CFTV Monitor v2.0 (Multi-Clientes)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import Response

@app.get("/snapshots/{filename}")
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

# --- MODELOS PYDANTIC ---

class ClientModel(BaseModel):
    id: Optional[str] = None
    name: str
    contact_name: Optional[str] = ""
    whatsapp: Optional[str] = ""
    notify_client: Optional[bool] = True
    notes: Optional[str] = ""

class CameraModel(BaseModel):
    id: Optional[str] = None
    name: str
    ip: str
    port: int = 554
    http_port: Optional[int] = 80
    nvr: Optional[str] = "N/A"
    channel: Optional[int] = 1
    client_id: Optional[str] = "default"
    username: Optional[str] = "admin"
    password: Optional[str] = ""
    snapshot_url: Optional[str] = ""

class BulkGenerateModel(BaseModel):
    mode: str = "dvr_channels" # "dvr_channels" ou "ip_range"
    client_id: Optional[str] = "default"
    # Modo DVR (Mesmo IP com múltiplos canais)
    dvr_name: Optional[str] = "Gravador NVD-01"
    dvr_ip: Optional[str] = "10.0.0.201"
    channel_start: Optional[int] = 1
    channel_end: Optional[int] = 16
    # Modo Faixa de IPs (Câmeras IP com IPs diferentes)
    prefix_name: Optional[str] = "Câmera"
    ip_start: Optional[str] = "192.168.1.100"
    count: Optional[int] = 10
    nvr: Optional[str] = "NVD-01"
    # Credenciais e portas
    port: int = 37777
    http_port: int = 80
    username: str = "admin"
    password: str = ""

class SettingsModel(BaseModel):
    check_interval: Optional[int] = None
    connection_timeout: Optional[float] = None
    failure_threshold: Optional[int] = None
    recovery_threshold: Optional[int] = None
    telegram: Optional[Dict[str, Any]] = None
    whatsapp: Optional[Dict[str, Any]] = None
    templates: Optional[Dict[str, str]] = None

class TestNotificationModel(BaseModel):
    channel: str
    target_number: Optional[str] = None

# --- ESTADO GLOBAL DA APLICAÇÃO ---

STATE = {
    "is_mock": False,
    "clients_file": CONFIG.clients_file,
    "cameras_file": CONFIG.cameras_file,
    "clients": [],
    "cameras": [],
    "tracker": None,
    "cycle": 0,
    "last_scan_time": "Nunca",
    "last_scan_duration_ms": 0,
    "event_subscribers": [],
    "is_scanning": False
}

def get_client_by_id(client_id: str) -> Optional[dict]:
    if not client_id:
        return None
    return next((c for c in STATE["clients"] if c.get("id") == client_id), None)

def load_clients_into_state(clients_path: str):
    if os.path.exists(clients_path):
        try:
            with open(clients_path, "r", encoding="utf-8") as f:
                STATE["clients"] = json.load(f)
        except Exception as e:
            print(f"[ERRO AO CARREGAR CLIENTES]: {e}")
            STATE["clients"] = []
    else:
        STATE["clients"] = []

def save_clients_to_file():
    try:
        with open(STATE["clients_file"], "w", encoding="utf-8") as f:
            json.dump(STATE["clients"], f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERRO AO SALVAR CLIENTES]: {e}")

def load_cameras_into_state(cameras_path: str):
    if os.path.exists(cameras_path):
        try:
            with open(cameras_path, "r", encoding="utf-8") as f:
                STATE["cameras"] = json.load(f)
        except Exception as e:
            print(f"[ERRO AO CARREGAR CÂMERAS]: {e}")
            STATE["cameras"] = []
    else:
        STATE["cameras"] = []

    STATE["tracker"] = DeviceTracker(
        STATE["cameras"],
        failure_threshold=CONFIG.failure_threshold,
        recovery_threshold=CONFIG.recovery_threshold,
        get_client_fn=get_client_by_id
    )

def save_cameras_to_file():
    try:
        with open(STATE["cameras_file"], "w", encoding="utf-8") as f:
            json.dump(STATE["cameras"], f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ERRO AO SALVAR CÂMERAS]: {e}")

async def notify_sse_subscribers(event_type: str, data: dict):
    payload = json.dumps({"type": event_type, "data": data, "timestamp": datetime.now().isoformat()})
    for dq in list(STATE["event_subscribers"]):
        try:
            await dq.put(payload)
        except Exception:
            STATE["event_subscribers"].remove(dq)

# Hooks do Notifier
original_down = Notifier.alert_camera_down
original_recovered = Notifier.alert_camera_recovered
original_nvr_down = Notifier.alert_nvr_down
original_nvr_recovered = Notifier.alert_nvr_recovered

def web_alert_down(camera: dict, failures: int, client_info: dict = None):
    original_down(camera, failures, client_info=client_info)
    client_name = (client_info.get("name") if client_info else None) or camera.get("client_name") or "Geral"
    asyncio.create_task(notify_sse_subscribers("ALERT", {
        "id": camera["id"],
        "name": camera["name"],
        "client_name": client_name,
        "ip": camera["ip"],
        "status": "OFFLINE",
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "failures": failures
    }))

def web_alert_recovered(camera: dict, client_info: dict = None):
    original_recovered(camera, client_info=client_info)
    client_name = (client_info.get("name") if client_info else None) or camera.get("client_name") or "Geral"
    asyncio.create_task(notify_sse_subscribers("ALERT", {
        "id": camera["id"],
        "name": camera["name"],
        "client_name": client_name,
        "ip": camera["ip"],
        "status": "ONLINE",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }))

def web_alert_nvr_down(nvr_name: str, dvr_ip: str, total_channels: int, offline_count: int, client_info: dict = None):
    original_nvr_down(nvr_name, dvr_ip, total_channels, offline_count, client_info=client_info)
    client_name = (client_info.get("name") if client_info else None) or "Geral"
    asyncio.create_task(notify_sse_subscribers("ALERT", {
        "id": f"nvr-{nvr_name}",
        "name": f"GRAVADOR {nvr_name}",
        "client_name": client_name,
        "ip": dvr_ip,
        "status": "OFFLINE",
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "failures": f"{offline_count}/{total_channels} canais"
    }))

def web_alert_nvr_recovered(nvr_name: str, dvr_ip: str, total_channels: int, client_info: dict = None):
    original_nvr_recovered(nvr_name, dvr_ip, total_channels, client_info=client_info)
    client_name = (client_info.get("name") if client_info else None) or "Geral"
    asyncio.create_task(notify_sse_subscribers("ALERT", {
        "id": f"nvr-{nvr_name}",
        "name": f"GRAVADOR {nvr_name}",
        "client_name": client_name,
        "ip": dvr_ip,
        "status": "ONLINE",
        "timestamp": datetime.now().strftime("%H:%M:%S")
    }))

Notifier.alert_camera_down = web_alert_down
Notifier.alert_camera_recovered = web_alert_recovered
Notifier.alert_nvr_down = web_alert_nvr_down
Notifier.alert_nvr_recovered = web_alert_nvr_recovered

async def trigger_camera_snapshot(cam_dict: dict):
    dev = STATE["tracker"].get_device(cam_dict["id"]) if STATE["tracker"] else None
    success, result_url = await capture_snapshot(cam_dict, is_mock=STATE["is_mock"])
    if dev:
        dev.last_snapshot_success = success
        if success:
            dev.last_snapshot_url = result_url
            dev.last_snapshot_time = datetime.now().strftime("%H:%M:%S")

async def perform_scan():
    if STATE["is_scanning"] or not STATE["tracker"]:
        return
    STATE["is_scanning"] = True
    
    start_time = time.perf_counter()
    sem = asyncio.Semaphore(CONFIG.max_concurrent_checks)
    timeout = CONFIG.connection_timeout

    async def check_single(dev_data):
        async with sem:
            cam_id = dev_data["id"]
            is_ok, latency = await check_camera_health(
                camera_data=dev_data,
                timeout=timeout,
                is_mock=STATE["is_mock"]
            )
            return cam_id, is_ok, latency

    tasks = [check_single(c) for c in list(STATE["cameras"])]
    if tasks:
        results = await asyncio.gather(*tasks)
        for cam_id, is_success, latency in results:
            dev = STATE["tracker"].get_device(cam_id)
            if dev:
                dev.update_result(is_success, latency)
                if is_success:
                    dev.last_snapshot_success = True
                    dev.last_snapshot_url = f"/snapshots/{cam_id}.jpg"
                    dev.last_snapshot_time = datetime.now().strftime("%H:%M:%S")

        STATE["tracker"].evaluate_nvrs()

    STATE["cycle"] += 1
    STATE["last_scan_duration_ms"] = round((time.perf_counter() - start_time) * 1000, 1)
    STATE["last_scan_time"] = datetime.now().strftime("%H:%M:%S")
    STATE["is_scanning"] = False

    await notify_sse_subscribers("STATUS_UPDATE", {})

async def background_monitoring_loop():
    await asyncio.sleep(1)
    for cam in STATE["cameras"]:
        asyncio.create_task(trigger_camera_snapshot(cam))
        
    while True:
        try:
            await perform_scan()
        except Exception as e:
            print(f"[ERRO NO MONITOR]: {e}")
        
        interval = max(CONFIG.check_interval, 5)
        await asyncio.sleep(interval)

# --- ROTAS DA API & DASHBOARD ---

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/status")
async def get_status(client_id: Optional[str] = None):
    if not STATE["tracker"]:
        return JSONResponse({"error": "Inicializando..."}, status_code=503)

    summary = STATE["tracker"].get_summary(client_id_filter=client_id)
    devices_list = []
    
    for cam in STATE["cameras"]:
        if client_id and client_id != "all" and cam.get("client_id") != client_id:
            continue

        dev_state = STATE["tracker"].get_device(cam["id"])
        if dev_state:
            client_obj = get_client_by_id(cam.get("client_id"))
            client_name = client_obj.get("name") if client_obj else "Geral"

            devices_list.append({
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
                "has_password": bool(cam.get("password")),
                "status": dev_state.status.value,
                "latency_ms": round(dev_state.last_latency_ms, 1),
                "failures": dev_state.consecutive_failures,
                "last_seen": dev_state.last_seen.strftime("%H:%M:%S"),
                "snapshot_url": dev_state.last_snapshot_url,
                "snapshot_time": dev_state.last_snapshot_time or dev_state.last_seen.strftime("%H:%M:%S"),
                "snapshot_success": dev_state.last_snapshot_success,
                "rtsp_url": get_rtsp_url(cam)
            })

    return {
        "summary": summary,
        "clients": STATE["clients"],
        "cycle": STATE["cycle"],
        "last_scan": STATE["last_scan_time"],
        "scan_time_ms": STATE["last_scan_duration_ms"],
        "is_mock": STATE["is_mock"],
        "devices": devices_list
    }

# --- CRUD DE CLIENTES ---

@app.get("/api/clients")
async def list_clients():
    return STATE["clients"]

@app.post("/api/clients")
async def create_client(client: ClientModel):
    new_id = client.id or f"cli-{uuid.uuid4().hex[:6]}"
    client_dict = client.model_dump()
    client_dict["id"] = new_id
    STATE["clients"].append(client_dict)
    save_clients_to_file()
    await notify_sse_subscribers("STATUS_UPDATE", {})
    return {"message": "Cliente cadastrado com sucesso", "client": client_dict}

@app.put("/api/clients/{client_id}")
async def update_client(client_id: str, client: ClientModel):
    for i, c in enumerate(STATE["clients"]):
        if c.get("id") == client_id:
            updated = client.model_dump()
            updated["id"] = client_id
            STATE["clients"][i] = updated
            save_clients_to_file()
            await notify_sse_subscribers("STATUS_UPDATE", {})
            return {"message": "Cliente atualizado com sucesso", "client": updated}
    raise HTTPException(status_code=404, detail="Cliente não encontrado")

@app.delete("/api/clients/{client_id}")
async def delete_client(client_id: str):
    initial_len = len(STATE["clients"])
    STATE["clients"] = [c for c in STATE["clients"] if c.get("id") != client_id]
    if len(STATE["clients"]) == initial_len:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    save_clients_to_file()
    await notify_sse_subscribers("STATUS_UPDATE", {})
    return {"message": "Cliente removido com sucesso"}

# --- CRUD DE CÂMERAS ---

@app.get("/api/cameras")
async def list_cameras(client_id: Optional[str] = None):
    if client_id and client_id != "all":
        return [c for c in STATE["cameras"] if c.get("client_id") == client_id]
    return STATE["cameras"]

@app.post("/api/cameras")
async def create_camera(camera: CameraModel):
    cam_id = camera.id or f"cam-{uuid.uuid4().hex[:6]}"
    cam_dict = camera.model_dump()
    cam_dict["id"] = cam_id
    
    # Preenche client_name
    client_obj = get_client_by_id(cam_dict.get("client_id"))
    cam_dict["client_name"] = client_obj.get("name") if client_obj else "Geral"

    STATE["cameras"].append(cam_dict)
    STATE["tracker"].add_or_update_device(cam_dict)
    save_cameras_to_file()

    asyncio.create_task(trigger_camera_snapshot(cam_dict))
    asyncio.create_task(perform_scan())
    return {"message": "Câmera cadastrada com sucesso", "camera": cam_dict}

@app.put("/api/cameras/{cam_id}")
async def update_camera(cam_id: str, camera: CameraModel):
    for i, c in enumerate(STATE["cameras"]):
        if c["id"] == cam_id:
            updated_dict = camera.model_dump()
            updated_dict["id"] = cam_id
            
            client_obj = get_client_by_id(updated_dict.get("client_id"))
            updated_dict["client_name"] = client_obj.get("name") if client_obj else "Geral"

            STATE["cameras"][i] = updated_dict
            STATE["tracker"].add_or_update_device(updated_dict)
            save_cameras_to_file()

            asyncio.create_task(trigger_camera_snapshot(updated_dict))
            asyncio.create_task(perform_scan())
            return {"message": "Câmera atualizada com sucesso", "camera": updated_dict}
    
    raise HTTPException(status_code=404, detail="Câmera não encontrada")

@app.delete("/api/cameras/{cam_id}")
async def delete_camera(cam_id: str):
    initial_len = len(STATE["cameras"])
    STATE["cameras"] = [c for c in STATE["cameras"] if c["id"] != cam_id]
    if len(STATE["cameras"]) == initial_len:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")
    
    STATE["tracker"].remove_device(cam_id)
    save_cameras_to_file()
    asyncio.create_task(perform_scan())
    return {"message": "Câmera removida com sucesso"}

@app.post("/api/cameras/bulk-generate")
async def bulk_generate(payload: BulkGenerateModel):
    new_cams = []
    client_obj = get_client_by_id(payload.client_id)
    client_name = client_obj.get("name") if client_obj else "Geral"

    if payload.mode == "dvr_channels":
        if not payload.dvr_ip or not payload.dvr_name:
            raise HTTPException(status_code=400, detail="Nome e IP do Gravador são obrigatórios")
        
        start_ch = max(1, payload.channel_start or 1)
        end_ch = max(start_ch, payload.channel_end or 16)
        total = (end_ch - start_ch) + 1
        dvr_ip_clean = payload.dvr_ip.strip()
        dvr_name_clean = payload.dvr_name.strip()
        
        for ch in range(start_ch, end_ch + 1):
            cam_dict = {
                "id": f"cam-{uuid.uuid4().hex[:6]}",
                "name": f"{dvr_name_clean} - Canal {ch:02d}",
                "ip": dvr_ip_clean,
                "port": payload.port,
                "http_port": payload.http_port,
                "nvr": dvr_name_clean,
                "channel": ch,
                "client_id": payload.client_id or "default",
                "client_name": client_name,
                "username": payload.username,
                "password": payload.password,
                "snapshot_url": f"http://{dvr_ip_clean}:{payload.http_port}/cgi-bin/snapshot.cgi?channel={ch}"
            }
            new_cams.append(cam_dict)
            STATE["cameras"].append(cam_dict)
            STATE["tracker"].add_or_update_device(cam_dict)
            asyncio.create_task(trigger_camera_snapshot(cam_dict))
            
        save_cameras_to_file()
        asyncio.create_task(perform_scan())
        return {"message": f"{total} canais do gravador '{dvr_name_clean}' cadastrados para '{client_name}'!"}
        
    else: # ip_range
        ip_parts = (payload.ip_start or "").split(".")
        if len(ip_parts) != 4:
            raise HTTPException(status_code=400, detail="Formato de IP inicial inválido")
        
        base_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}"
        start_num = int(ip_parts[3])
        count = payload.count or 10
        
        for i in range(count):
            cur_num = start_num + i
            cam_dict = {
                "id": f"cam-{uuid.uuid4().hex[:6]}",
                "name": f"{payload.prefix_name} {i+1:02d}",
                "ip": f"{base_ip}.{cur_num}",
                "port": payload.port,
                "http_port": payload.http_port,
                "nvr": payload.nvr or "N/A",
                "channel": i + 1,
                "client_id": payload.client_id or "default",
                "client_name": client_name,
                "username": payload.username,
                "password": payload.password,
                "snapshot_url": ""
            }
            new_cams.append(cam_dict)
            STATE["cameras"].append(cam_dict)
            STATE["tracker"].add_or_update_device(cam_dict)
            asyncio.create_task(trigger_camera_snapshot(cam_dict))

        save_cameras_to_file()
        asyncio.create_task(perform_scan())
        return {"message": f"{count} câmeras cadastradas para '{client_name}'!"}

@app.post("/api/cameras/{cam_id}/snapshot")
async def force_snapshot(cam_id: str):
    cam = next((c for c in STATE["cameras"] if c["id"] == cam_id), None)
    if not cam:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")
    
    success, url = await capture_snapshot(cam, is_mock=STATE["is_mock"])
    dev = STATE["tracker"].get_device(cam_id)
    if dev:
        dev.last_snapshot_success = success
        dev.last_snapshot_url = url
        dev.last_snapshot_time = datetime.now().strftime("%H:%M:%S")
    
    await notify_sse_subscribers("STATUS_UPDATE", {})
    return {"success": success, "url": url}

@app.get("/api/settings")
async def get_settings():
    return CONFIG.data

@app.post("/api/settings")
async def update_settings(payload: SettingsModel):
    update_dict = {k: v for k, v in payload.model_dump().items() if v is not None}
    CONFIG.update(update_dict)
    
    if STATE["tracker"]:
        STATE["tracker"].failure_threshold = CONFIG.failure_threshold
        STATE["tracker"].recovery_threshold = CONFIG.recovery_threshold
        for dev in STATE["tracker"].devices.values():
            dev.failure_threshold = CONFIG.failure_threshold
            dev.recovery_threshold = CONFIG.recovery_threshold

    await notify_sse_subscribers("STATUS_UPDATE", {})
    return {"message": "Configurações atualizadas com sucesso", "settings": CONFIG.data}

@app.post("/api/test-notification")
async def test_notification_route(payload: TestNotificationModel):
    success, msg = await Notifier.test_notification(payload.channel, target_number=payload.target_number)
    return {"success": success, "message": msg}

@app.post("/api/scan-now")
async def scan_now():
    asyncio.create_task(perform_scan())
    return {"message": "Varredura iniciada"}

@app.get("/api/events")
async def sse_events(request: Request):
    async def event_generator():
        q = asyncio.Queue()
        STATE["event_subscribers"].append(q)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            if q in STATE["event_subscribers"]:
                STATE["event_subscribers"].remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

if __name__ == "__main__":
    import uvicorn
    # A v2.0 roda na porta 8001
    port = CONFIG.server_port or 8001
    print(f"\n=======================================================")
    print(f"🚀 INICIANDO CFTV MONITOR v2.0 (MULTI-CLIENTES)")
    print(f"🌐 ACESSE NO NAVEGADOR: http://localhost:{port}")
    print(f"=======================================================\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
