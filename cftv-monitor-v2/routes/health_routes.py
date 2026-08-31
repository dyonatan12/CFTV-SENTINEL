import time
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Response
from config import CONFIG
from state.app_state import GLOBAL_STATE

router = APIRouter(tags=["Health & Métricas"])

START_TIME = time.time()

@router.get("/api/health")
async def health_check():
    GLOBAL_STATE.ensure_tracker_initialized()
    summary = GLOBAL_STATE.tracker.get_summary() if GLOBAL_STATE.tracker else {"total": 0, "online": 0, "offline": 0}
    uptime_seconds = int(time.time() - START_TIME)

    # Checa status do Gateway WhatsApp se configurado
    gateway_status = "disabled"
    if CONFIG.whatsapp.get("enabled"):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{CONFIG.whatsapp.get('api_url')}/health")
                if res.status_code == 200:
                    gateway_status = "online"
                else:
                    gateway_status = f"error_http_{res.status_code}"
        except Exception:
            gateway_status = "offline"

    return {
        "status": "healthy",
        "service": "cftv-monitor-v2",
        "version": "2.0.0",
        "uptime_seconds": uptime_seconds,
        "cycle": GLOBAL_STATE.cycle,
        "last_scan_time": GLOBAL_STATE.last_scan_time,
        "last_scan_duration_ms": GLOBAL_STATE.last_scan_duration_ms,
        "devices": summary,
        "whatsapp_gateway": gateway_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.get("/api/ready")
async def readiness_check():
    # Verifica se as listas e o tracker foram carregados
    if GLOBAL_STATE.tracker is None:
        return Response(content='{"status": "not_ready", "reason": "tracker_initializing"}', media_type="application/json", status_code=503)
    return {"status": "ready"}

@router.get("/metrics")
async def prometheus_metrics():
    GLOBAL_STATE.ensure_tracker_initialized()
    summary = GLOBAL_STATE.tracker.get_summary() if GLOBAL_STATE.tracker else {"total": 0, "online": 0, "offline": 0, "pending": 0}
    uptime_seconds = int(time.time() - START_TIME)

    metrics_text = f"""# HELP cftv_uptime_seconds Tempo de atividade da aplicacao em segundos
# TYPE cftv_uptime_seconds counter
cftv_uptime_seconds {uptime_seconds}

# HELP cftv_cameras_total Total de cameras cadastradas
# TYPE cftv_cameras_total gauge
cftv_cameras_total {summary.get('total', 0)}

# HELP cftv_cameras_online Quantidade de cameras com status ONLINE
# TYPE cftv_cameras_online gauge
cftv_cameras_online {summary.get('online', 0)}

# HELP cftv_cameras_offline Quantidade de cameras com status OFFLINE
# TYPE cftv_cameras_offline gauge
cftv_cameras_offline {summary.get('offline', 0)}

# HELP cftv_cameras_pending Quantidade de cameras com status pendente
# TYPE cftv_cameras_pending gauge
cftv_cameras_pending {summary.get('pending', 0)}

# HELP cftv_scan_cycle_total Total de ciclos de varredura executados
# TYPE cftv_scan_cycle_total counter
cftv_scan_cycle_total {GLOBAL_STATE.cycle}

# HELP cftv_scan_duration_ms Duracao da ultima varredura em milissegundos
# TYPE cftv_scan_duration_ms gauge
cftv_scan_duration_ms {GLOBAL_STATE.last_scan_duration_ms}
"""
    return Response(content=metrics_text, media_type="text/plain; version=0.0.4")
