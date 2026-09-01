import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

DEFAULT_TEMPLATES = {
    "camera_down": "🚨 *ALERTA CFTV: CÂMERA OFFLINE!*\n\n📸 *Câmera:* {camera_name}\n🌐 *IP:* {camera_ip}:{camera_port}\n📼 *Gravador:* {nvr_name} (Canal {channel})\n⚠️ *Status:* Desconectada ({failures} falhas)\n🕒 *Horário:* {timestamp}",
    
    "camera_recovered": "✅ *CFTV NORMALIZADO: CÂMERA ONLINE!*\n\n📸 *Câmera:* {camera_name}\n🌐 *IP:* {camera_ip}\n📼 *Gravador:* {nvr_name} (Canal {channel})\n🕒 *Horário:* {timestamp}",
    
    "nvr_down": "🚨 *ALERTA CRÍTICO: GRAVADOR OFFLINE!*\n\n📼 *Gravador:* {nvr_name}\n🌐 *IP:* {camera_ip}\n⚠️ *Status:* Gravador desconectou ({offline_count}/{total_channels} canais sem sinal)\n🕒 *Horário:* {timestamp}",
    
    "nvr_recovered": "✅ *CFTV NORMALIZADO: GRAVADOR ONLINE!*\n\n📼 *Gravador:* {nvr_name}\n🌐 *IP:* {camera_ip}\n📶 *Status:* Gravador e todos os {total_channels} canais restabelecidos com sucesso\n🕒 *Horário:* {timestamp}"
}

DEFAULT_SETTINGS = {
    "server_port": 8000,
    "check_interval": 45,
    "connection_timeout": 3.5,
    "failure_threshold": 3,
    "recovery_threshold": 2,
    "max_concurrent_checks": 8,
    "cameras_file": os.path.join(BASE_DIR, "cameras.json"),
    "log_file": os.path.join(BASE_DIR, "cftv_monitor.log"),
    "telegram": {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
        "send_snapshot": True
    },
    "whatsapp": {
        "enabled": False,
        "provider": "evolution",
        "api_url": "http://localhost:8080",
        "api_key": "",
        "instance_name": "cftv",
        "target_number": "",
        "send_snapshot": True
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
                print(f"[ERRO AO CARREGAR SETTINGS]: {e}")
        else:
            self.save()

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERRO AO SALVAR SETTINGS]: {e}")

    def update(self, new_data: dict):
        for k, v in new_data.items():
            if isinstance(v, dict) and k in self.data and isinstance(self.data[k], dict):
                self.data[k].update(v)
            else:
                self.data[k] = v
        self.save()

    @property
    def check_interval(self) -> int:
        return int(self.data.get("check_interval", 45))

    @property
    def connection_timeout(self) -> float:
        return float(self.data.get("connection_timeout", 3.5))

    @property
    def failure_threshold(self) -> int:
        return int(self.data.get("failure_threshold", 3))

    @property
    def recovery_threshold(self) -> int:
        return int(self.data.get("recovery_threshold", 2))

    @property
    def max_concurrent_checks(self) -> int:
        return int(self.data.get("max_concurrent_checks", 8))

    @property
    def cameras_file(self) -> str:
        raw = self.data.get("cameras_file", "cameras.json")
        return self._resolve_path(raw, "cameras.json")

    @property
    def log_file(self) -> str:
        raw = self.data.get("log_file", "cftv_monitor.log")
        return self._resolve_path(raw, "cftv_monitor.log")

    @property
    def telegram(self) -> dict:
        return self.data.get("telegram", {})

    @property
    def whatsapp(self) -> dict:
        return self.data.get("whatsapp", {})

    @property
    def templates(self) -> dict:
        return self.data.get("templates", DEFAULT_TEMPLATES)

CONFIG = SystemSettings()
