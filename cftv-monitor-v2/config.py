import os
import json

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")
CLIENTS_FILE = os.path.join(os.path.dirname(__file__), "clients.json")

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
    "server_port": 8001,
    "check_interval": 45,
    "connection_timeout": 3.5,
    "failure_threshold": 3,
    "recovery_threshold": 2,
    "max_concurrent_checks": 8,
    "cameras_file": os.path.join(os.path.dirname(__file__), "cameras.json"),
    "clients_file": CLIENTS_FILE,
    "log_file": os.path.join(os.path.dirname(__file__), "cftv_monitor.log"),
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
    def server_port(self) -> int:
        return int(self.data.get("server_port", 8001))

    @property
    def check_interval(self) -> int:
        return int(self.data.get("check_interval", 15))

    @property
    def connection_timeout(self) -> float:
        return float(self.data.get("connection_timeout", 2.0))

    @property
    def failure_threshold(self) -> int:
        return int(self.data.get("failure_threshold", 3))

    @property
    def recovery_threshold(self) -> int:
        return int(self.data.get("recovery_threshold", 2))

    @property
    def max_concurrent_checks(self) -> int:
        return int(self.data.get("max_concurrent_checks", 50))

    @property
    def cameras_file(self) -> str:
        return self.data.get("cameras_file", os.path.join(os.path.dirname(__file__), "cameras.json"))

    @property
    def clients_file(self) -> str:
        return self.data.get("clients_file", CLIENTS_FILE)

    @property
    def log_file(self) -> str:
        return self.data.get("log_file", os.path.join(os.path.dirname(__file__), "cftv_monitor.log"))

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
