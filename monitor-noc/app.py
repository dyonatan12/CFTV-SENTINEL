import sys
import asyncio
from contextlib import asynccontextmanager

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CONFIG
from state.app_state import GLOBAL_STATE
from routes import (
    dashboard_router,
    auth_router,
    camera_router,
    client_router,
    settings_router,
    event_router,
    health_router,
    alert_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    GLOBAL_STATE.load_clients()
    GLOBAL_STATE.load_cameras()
    task = asyncio.create_task(GLOBAL_STATE.background_monitoring_loop())
    yield
    task.cancel()

app = FastAPI(
    title="CFTV Sentinel NOC v2.0",
    description="Central de Monitoramento CFTV com Segurança Avançada, Arquitetura Modular, Histórico em SQLite e RBAC",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CONFIG.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(auth_router)
app.include_router(camera_router)
app.include_router(client_router)
app.include_router(settings_router)
app.include_router(event_router)
app.include_router(health_router)
app.include_router(alert_router)

if __name__ == "__main__":
    import uvicorn
    port = CONFIG.server_port or 8001
    print(f"\n=======================================================")
    print(f"🛡️ INICIANDO CFTV SENTINEL v2.0 (MODULAR + SQLITE)")
    print(f"🌐 ACESSE NO NAVEGADOR: http://localhost:{port}")
    print(f"=======================================================\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
