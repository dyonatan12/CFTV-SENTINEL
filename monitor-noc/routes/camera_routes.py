import uuid
import asyncio
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends

from models.schemas import CameraModel, BulkGenerateModel
from core.security import encrypt_secret, sanitize_device_for_api
from core.auth import require_operator_or_admin, get_current_active_user
from core.snapshot import capture_snapshot
from state.app_state import GLOBAL_STATE

router = APIRouter(prefix="/api/cameras", tags=["Câmeras"])

@router.get("")
async def list_cameras(client_id: Optional[str] = None):
    cams = GLOBAL_STATE.cameras
    if client_id and client_id != "all":
        cams = [c for c in cams if c.get("client_id") == client_id]
    return [sanitize_device_for_api(c) for c in cams]

@router.post("", dependencies=[Depends(require_operator_or_admin)])
async def create_camera(camera: CameraModel):
    GLOBAL_STATE.ensure_tracker_initialized()
    cam_id = camera.id or f"cam-{uuid.uuid4().hex[:6]}"
    cam_dict = camera.model_dump()
    cam_dict["id"] = cam_id
    
    if cam_dict.get("password"):
        cam_dict["password"] = encrypt_secret(cam_dict["password"])
    
    client_obj = GLOBAL_STATE.get_client_by_id(cam_dict.get("client_id"))
    cam_dict["client_name"] = client_obj.get("name") if client_obj else "Geral"

    GLOBAL_STATE.cameras.append(cam_dict)
    if GLOBAL_STATE.tracker:
        GLOBAL_STATE.tracker.add_or_update_device(cam_dict)
    GLOBAL_STATE.save_cameras()

    asyncio.create_task(GLOBAL_STATE.trigger_camera_snapshot(cam_dict))
    asyncio.create_task(GLOBAL_STATE.perform_scan())
    return {"message": "Câmera cadastrada com sucesso", "camera": sanitize_device_for_api(cam_dict)}

@router.put("/{cam_id}", dependencies=[Depends(require_operator_or_admin)])
async def update_camera(cam_id: str, camera: CameraModel):
    GLOBAL_STATE.ensure_tracker_initialized()
    for i, c in enumerate(GLOBAL_STATE.cameras):
        if c["id"] == cam_id:
            updated_dict = camera.model_dump()
            updated_dict["id"] = cam_id
            
            if updated_dict.get("password") in ["********", ""]:
                updated_dict["password"] = c.get("password", "")
            else:
                updated_dict["password"] = encrypt_secret(updated_dict["password"])

            client_obj = GLOBAL_STATE.get_client_by_id(updated_dict.get("client_id"))
            updated_dict["client_name"] = client_obj.get("name") if client_obj else "Geral"

            GLOBAL_STATE.cameras[i] = updated_dict
            if GLOBAL_STATE.tracker:
                GLOBAL_STATE.tracker.add_or_update_device(updated_dict)
            GLOBAL_STATE.save_cameras()

            asyncio.create_task(GLOBAL_STATE.trigger_camera_snapshot(updated_dict))
            asyncio.create_task(GLOBAL_STATE.perform_scan())
            return {"message": "Câmera atualizada com sucesso", "camera": sanitize_device_for_api(updated_dict)}
    
    raise HTTPException(status_code=404, detail="Câmera não encontrada")

@router.delete("/{cam_id}", dependencies=[Depends(require_operator_or_admin)])
async def delete_camera(cam_id: str):
    GLOBAL_STATE.ensure_tracker_initialized()
    initial_len = len(GLOBAL_STATE.cameras)
    GLOBAL_STATE.cameras = [c for c in GLOBAL_STATE.cameras if c["id"] != cam_id]
    if len(GLOBAL_STATE.cameras) == initial_len:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")
    
    if GLOBAL_STATE.tracker:
        GLOBAL_STATE.tracker.remove_device(cam_id)
    GLOBAL_STATE.save_cameras()
    asyncio.create_task(GLOBAL_STATE.perform_scan())
    return {"message": "Câmera removida com sucesso"}

@router.post("/bulk-generate", dependencies=[Depends(require_operator_or_admin)])
async def bulk_generate(payload: BulkGenerateModel):
    GLOBAL_STATE.ensure_tracker_initialized()
    new_cams = []
    client_obj = GLOBAL_STATE.get_client_by_id(payload.client_id)
    client_name = client_obj.get("name") if client_obj else "Geral"
    enc_password = encrypt_secret(payload.password) if payload.password else ""

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
                "password": enc_password,
                "snapshot_url": f"http://{dvr_ip_clean}:{payload.http_port}/cgi-bin/snapshot.cgi?channel={ch}"
            }
            new_cams.append(cam_dict)
            GLOBAL_STATE.cameras.append(cam_dict)
            if GLOBAL_STATE.tracker:
                GLOBAL_STATE.tracker.add_or_update_device(cam_dict)
            asyncio.create_task(GLOBAL_STATE.trigger_camera_snapshot(cam_dict))
            
        GLOBAL_STATE.save_cameras()
        asyncio.create_task(GLOBAL_STATE.perform_scan())
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
                "password": enc_password,
                "snapshot_url": ""
            }
            new_cams.append(cam_dict)
            GLOBAL_STATE.cameras.append(cam_dict)
            if GLOBAL_STATE.tracker:
                GLOBAL_STATE.tracker.add_or_update_device(cam_dict)
            asyncio.create_task(GLOBAL_STATE.trigger_camera_snapshot(cam_dict))

        GLOBAL_STATE.save_cameras()
        asyncio.create_task(GLOBAL_STATE.perform_scan())
        return {"message": f"{count} câmeras cadastradas para '{client_name}'!"}

@router.post("/{cam_id}/snapshot", dependencies=[Depends(require_operator_or_admin)])
async def force_snapshot(cam_id: str):
    GLOBAL_STATE.ensure_tracker_initialized()
    cam = next((c for c in GLOBAL_STATE.cameras if c["id"] == cam_id), None)
    if not cam:
        raise HTTPException(status_code=404, detail="Câmera não encontrada")
    
    success, url = await capture_snapshot(cam, is_mock=GLOBAL_STATE.is_mock)
    dev = GLOBAL_STATE.tracker.get_device(cam_id) if GLOBAL_STATE.tracker else None
    if dev:
        dev.last_snapshot_success = success
        dev.last_snapshot_url = url
        dev.last_snapshot_time = datetime.now().strftime("%H:%M:%S")
    
    await GLOBAL_STATE.broadcast_sse("STATUS_UPDATE", {})
    return {"success": success, "url": url}
