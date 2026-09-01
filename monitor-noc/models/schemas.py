from typing import Optional, List, Dict, Any
from pydantic import BaseModel

# --- MODELOS DE CLIENTES ---
class ClientModel(BaseModel):
    id: Optional[str] = None
    name: str
    contact_name: Optional[str] = ""
    whatsapp: Optional[str] = ""
    notify_client: Optional[bool] = True
    lat: Optional[float] = None
    lng: Optional[float] = None
    notes: Optional[str] = ""

# --- MODELOS DE CÂMERAS ---
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
    custom_timeout: Optional[float] = None
    custom_failure_threshold: Optional[int] = None
    custom_recovery_threshold: Optional[int] = None

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

# --- MODELOS DE CONFIGURAÇÕES ---
class SettingsModel(BaseModel):
    check_interval: Optional[int] = None
    connection_timeout: Optional[float] = None
    failure_threshold: Optional[int] = None
    recovery_threshold: Optional[int] = None
    max_concurrent_checks: Optional[int] = None
    telegram: Optional[Dict[str, Any]] = None
    whatsapp: Optional[Dict[str, Any]] = None
    templates: Optional[Dict[str, str]] = None

class TestNotificationModel(BaseModel):
    channel: str
    target_number: Optional[str] = None

# --- MODELOS DE AUTENTICAÇÃO ---
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    name: str
    role: str = "operator"
