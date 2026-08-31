from .auth_routes import router as auth_router
from .camera_routes import router as camera_router
from .client_routes import router as client_router
from .settings_routes import router as settings_router
from .event_routes import router as event_router
from .dashboard_routes import router as dashboard_router
from .health_routes import router as health_router
from .alert_routes import router as alert_router

__all__ = [
    "auth_router",
    "camera_router",
    "client_router",
    "settings_router",
    "event_router",
    "dashboard_router",
    "health_router",
    "alert_router"
]
