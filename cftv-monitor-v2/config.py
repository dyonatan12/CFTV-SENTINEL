import os
import json
import logging

logger = logging.getLogger("cftv.config")

# Carrega .env se python-dotenv estiver instalado
try:
    from dotenv import load_dotenv
    # Procura .env na pasta local ou na raiz do projeto
    local_env = os.path.join(os.path.dirname(__file__), ".env")
    root_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(local_env):
        load_dotenv(local_env)
    elif os.path.exists(root_env):
        load_dotenv(root_env)
    else:
        load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
CLIENTS_FILE = os.path.join(BASE_DIR, "clients.json")

DEFAULT_TEMPLATES = {
    # Templates para a Central / NOC Interno (Técnico)
    "noc_camera_down": "🚨 *[NOC INTERNO] ALERTA: CÂMERA OFFLINE!*\n\n🏢 *Cliente:* {client_name}\n📸 *Câmera:* {camera_name}\n🌐 *IP:* {camera_ip}:{camera_port}\n📼 *Gravador:* {nvr_name} (Canal {channel})\n⚠️ *Status:* Desconectada ({failures} falhas)\n🕒 *Horário:* {timestamp}",
    
    "noc_camera_recovered": "✅ *[NOC INTERNO] CÂMERA ONLINE!*\n\n🏢 *Cliente:* {client_name}\n📸 *Câmera:* {camera_name}\n🌐 *IP:* {camera_ip}\n📼 *Gravador:* {nvr_name} (Canal {channel})\n🕒 *Horário:* {timestamp}",
    
    "noc_nvr_down": "🚨 *[NOC INTERNO] ALERTA CRÍTICO: GRAVADOR OFFLINE!*\n\n🏢 *Cliente:* {client_name}\n📼 *Gravador:* {nvr_name}\n🌐 *IP:* {camera_ip}\n⚠️ *Status:* Gravador desconectou ({offline_count}/{total_channels} canais sem sinal)\n🕒 *Horário:* {timestamp}",
    
    "noc_nvr_recovered": "✅ *[NOC INTERNO] GRAVADOR RESTABELECIDO!*\n\n🏢 *Cliente:* {client_name}\n📼 *Gravador:* {nvr_name}\n🌐 *IP:* {camera_ip}\n📶 *Status:* Gravador e todos os {total_channels} canais restabelecidos\n🕒 *Horário:* {timestamp}",

    # Templates para o Cliente Final (Amigável & Cordial)
    "client_camera_down": "Olá, {contact_name}! 👋\n\nIdentificamos uma oscilação no seu sistema de CFTV:\n🏢 *Unidade:* {client_name}\n📸 *Dispositivo:* {camera_name}\n🕒 *Horário:* {timestamp}\n\nNossa central de monitoramento já está acompanhando para normalização rápida. 🛡️",
    
    "client_camera_recovered": "Olá, {contact_name}! 👋\n\nInformamos que a conexão com a câmera *{camera_name}* do *{client_name}* foi *totalmente restabelecida* e está operando normalmente. ✅",
    
    "client_nvr_down": "Olá, {contact_name}! 👋\n\n🚨 *Aviso de Oscilação de Conexão:*\nIdentificamos que o gravador de vídeo *{nvr_name}* da sua empresa (*{client_name}*) perdeu conexão com a internet ou energia.\n🕒 *Horário:* {timestamp}\n\nNossa equipe técnica já está em alerta e monitorando o restabelecimento do sinal. 🛡️",
    
    "client_nvr_recovered": "Olá, {contact_name}! 👋\n\n✅ *Sistema de Segurança Normalizado!*\nO gravador de vídeo *{nvr_name}* do *{client_name}* retornou e todas as suas câmeras já estão gravando normalmente."
}

DEFAULT_SETTINGS = {
    "server_port": int(os.getenv("SERVER_PORT", "8001")),
    "check_interval": int(os.getenv("CHECK_INTERVAL", "45")),
    "connection_timeout": float(os.getenv("CONNECTION_TIMEOUT", "3.5")),
    "failure_threshold": int(os.getenv("FAILURE_THRESHOLD", "3")),
    "recovery_threshold": int(os.getenv("RECOVERY_THRESHOLD", "2")),
    "max_concurrent_checks": int(os.getenv("MAX_CONCURRENT_CHECKS", "8")),
    "cameras_file": os.path.join(BASE_DIR, "cameras.json"),
    "clients_file": CLIENTS_FILE,
    "log_file": os.path.join(BASE_DIR, "cftv_monitor.log"),
    "telegram": {
        "enabled": os.getenv("TELEGRAM_ENABLED", "false").lower() == "true",
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        "send_snapshot": os.getenv("TELEGRAM_SEND_SNAPSHOT", "true").lower() == "true"
    },
    "whatsapp": {
        "enabled": os.getenv("WHATSAPP_ENABLED", "false").lower() == "true",
        "provider": "evolution",
        "api_url": os.getenv("WHATSAPP_API_URL", "http://localhost:8080"),
        "api_key": os.getenv("WHATSAPP_API_KEY", ""),
        "instance_name": os.getenv("WHATSAPP_INSTANCE", "cftv"),
        "target_number": os.getenv("WHATSAPP_TARGET_NUMBER", ""),
        "send_snapshot": os.getenv("WHATSAPP_SEND_SNAPSHOT", "true").lower() == "true"
    },
    "templates": DEFAULT_TEMPLATES
}

class SystemSettings:
    def __init__(self):
        self.data = dict(DEFAULT_SETTINGS)
        self.load()

    def _resolve_path(self, val: str, default_filename: str) -> str:
        if not val or not isinstance(val, str):
            return os.path.join(BASE_DIR, default_filename)
        if os.path.isabs(val) and os.path.exists(os.path.dirname(val)):
            return val
        return os.path.join(BASE_DIR, os.path.basename(val))

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
                    if "templates" not in self.data or not isinstance(self.data["templates"], dict):
                        self.data["templates"] = dict(DEFAULT_TEMPLATES)
                    else:
                        for k, v in DEFAULT_TEMPLATES.items():
                            if k not in self.data["templates"]:
                                self.data["templates"][k] = v
            except Exception as e:
                logger.error(f"[ERRO AO CARREGAR SETTINGS]: {e}")
        else:
            self.save()

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[ERRO AO SALVAR SETTINGS]: {e}")

    def update(self, new_data: dict):
        for k, v in new_data.items():
            if isinstance(v, dict) and k in self.data and isinstance(self.data[k], dict):
                self.data[k].update(v)
            else:
                self.data[k] = v
        self.save()

    @property
    def server_port(self) -> int:
        return int(os.getenv("SERVER_PORT", self.data.get("server_port", 8001)))

    @property
    def check_interval(self) -> int:
        return int(os.getenv("CHECK_INTERVAL", self.data.get("check_interval", 45)))

    @property
    def connection_timeout(self) -> float:
        return float(os.getenv("CONNECTION_TIMEOUT", self.data.get("connection_timeout", 3.5)))

    @property
    def failure_threshold(self) -> int:
        return int(os.getenv("FAILURE_THRESHOLD", self.data.get("failure_threshold", 3)))

    @property
    def recovery_threshold(self) -> int:
        return int(os.getenv("RECOVERY_THRESHOLD", self.data.get("recovery_threshold", 2)))

    @property
    def max_concurrent_checks(self) -> int:
        return int(os.getenv("MAX_CONCURRENT_CHECKS", self.data.get("max_concurrent_checks", 8)))

    @property
    def cameras_file(self) -> str:
        raw = self.data.get("cameras_file", "cameras.json")
        return self._resolve_path(raw, "cameras.json")

    @property
    def clients_file(self) -> str:
        raw = self.data.get("clients_file", "clients.json")
        return self._resolve_path(raw, "clients.json")

    @property
    def log_file(self) -> str:
        raw = self.data.get("log_file", "cftv_monitor.log")
        return self._resolve_path(raw, "cftv_monitor.log")

    @property
    def allowed_origins(self) -> list:
        origins = os.getenv("ALLOWED_ORIGINS", "")
        if origins:
            return [o.strip() for o in origins.split(",") if o.strip()]
        return ["http://localhost:8001", "http://127.0.0.1:8001", "http://localhost:3000"]

    @property
    def telegram(self) -> dict:
        t = dict(self.data.get("telegram", {}))
        if os.getenv("TELEGRAM_BOT_TOKEN"):
            t["bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN")
        if os.getenv("TELEGRAM_CHAT_ID"):
            t["chat_id"] = os.getenv("TELEGRAM_CHAT_ID")
        if os.getenv("TELEGRAM_ENABLED"):
            t["enabled"] = os.getenv("TELEGRAM_ENABLED").lower() == "true"
        return t

    @property
    def whatsapp(self) -> dict:
        w = dict(self.data.get("whatsapp", {}))
        if os.getenv("WHATSAPP_API_URL"):
            w["api_url"] = os.getenv("WHATSAPP_API_URL")
        if os.getenv("WHATSAPP_API_KEY"):
            w["api_key"] = os.getenv("WHATSAPP_API_KEY")
        if os.getenv("WHATSAPP_INSTANCE"):
            w["instance_name"] = os.getenv("WHATSAPP_INSTANCE")
        if os.getenv("WHATSAPP_TARGET_NUMBER"):
            w["target_number"] = os.getenv("WHATSAPP_TARGET_NUMBER")
        if os.getenv("WHATSAPP_ENABLED"):
            w["enabled"] = os.getenv("WHATSAPP_ENABLED").lower() == "true"
        return w

    @property
    def templates(self) -> dict:
        return self.data.get("templates", DEFAULT_TEMPLATES)

CONFIG = SystemSettings()
