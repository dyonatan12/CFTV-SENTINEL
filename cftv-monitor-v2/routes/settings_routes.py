import asyncio
from fastapi import APIRouter, HTTPException, Depends

from config import CONFIG
from models.schemas import SettingsModel, TestNotificationModel
from core.auth import require_admin, require_operator_or_admin
from core.notifier import Notifier
from state.app_state import GLOBAL_STATE

router = APIRouter(prefix="/api", tags=["Configurações"])

@router.get("/settings", dependencies=[Depends(require_admin)])
async def get_settings():
    safe_settings = dict(CONFIG.data)
    if "telegram" in safe_settings and safe_settings["telegram"].get("bot_token"):
        safe_settings["telegram"]["bot_token"] = "********"
    if "whatsapp" in safe_settings and safe_settings["whatsapp"].get("api_key"):
        safe_settings["whatsapp"]["api_key"] = "********"
    return safe_settings

@router.post("/settings", dependencies=[Depends(require_admin)])
async def update_settings(payload: SettingsModel):
    update_dict = {k: v for k, v in payload.model_dump().items() if v is not None}
    
    if "telegram" in update_dict and update_dict["telegram"].get("bot_token") == "********":
        update_dict["telegram"]["bot_token"] = CONFIG.telegram.get("bot_token", "")
    if "whatsapp" in update_dict and update_dict["whatsapp"].get("api_key") == "********":
        update_dict["whatsapp"]["api_key"] = CONFIG.whatsapp.get("api_key", "")

    CONFIG.update(update_dict)
    
    GLOBAL_STATE.ensure_tracker_initialized()
    if GLOBAL_STATE.tracker:
        GLOBAL_STATE.tracker.failure_threshold = CONFIG.failure_threshold
        GLOBAL_STATE.tracker.recovery_threshold = CONFIG.recovery_threshold
        for dev in GLOBAL_STATE.tracker.devices.values():
            dev.failure_threshold = CONFIG.failure_threshold
            dev.recovery_threshold = CONFIG.recovery_threshold

    await GLOBAL_STATE.broadcast_sse("STATUS_UPDATE", {})
    return {"message": "Configurações atualizadas com sucesso", "settings": CONFIG.data}

@router.post("/test-notification", dependencies=[Depends(require_operator_or_admin)])
async def test_notification_route(payload: TestNotificationModel):
    success, msg = await Notifier.test_notification(payload.channel, target_number=payload.target_number)
    return {"success": success, "message": msg}

@router.post("/scan-now", dependencies=[Depends(require_operator_or_admin)])
async def scan_now():
    asyncio.create_task(GLOBAL_STATE.perform_scan())
    return {"message": "Varredura iniciada"}
