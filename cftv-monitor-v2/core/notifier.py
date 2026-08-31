import os
import sys
import logging
import httpx
import asyncio
import re
from datetime import datetime
from config import CONFIG
from core.event_bus import EVENT_BUS

logger = logging.getLogger("cftv.notifier")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT_DIR = os.path.join(BASE_DIR, "snapshots")

def format_template(template_str: str, context: dict) -> str:
    result = template_str
    for k, v in context.items():
        result = result.replace(f"{{{k}}}", str(v if v is not None else ""))
    return result

def convert_to_html(text: str) -> str:
    text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    return text

def _safe_schedule_task(coro):
    try:
        loop = asyncio.get_running_loop()
        return loop.create_task(coro)
    except RuntimeError:
        try:
            coro.close()
        except Exception:
            pass
        return None

class NotificationService:
    def __init__(self, config=CONFIG):
        self.config = config
        self.last_alert_timestamps = {}
        self.cooldown_seconds = 600 # 10 minutos anti-flapping

    def should_suppress_flood(self, device_key: str) -> bool:
        now = datetime.now().timestamp()
        last = self.last_alert_timestamps.get(device_key, 0)
        if (now - last) < self.cooldown_seconds:
            return True
        self.last_alert_timestamps[device_key] = now
        return False

    async def send_telegram(self, text: str, image_path: str = None) -> tuple[bool, str]:
        tg = self.config.telegram
        if not tg.get("enabled") or not tg.get("bot_token") or not tg.get("chat_id"):
            return False, "Telegram não habilitado ou credenciais ausentes"

        token = tg["bot_token"].strip()
        chat_id = tg["chat_id"].strip()
        send_snapshot = tg.get("send_snapshot", True)
        html_text = convert_to_html(text)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if send_snapshot and image_path and os.path.exists(image_path):
                    url = f"https://api.telegram.org/bot{token}/sendPhoto"
                    with open(image_path, "rb") as f:
                        files = {"photo": f}
                        data = {"chat_id": chat_id, "caption": html_text, "parse_mode": "HTML"}
                        res = await client.post(url, data=data, files=files)
                else:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    data = {"chat_id": chat_id, "text": html_text, "parse_mode": "HTML"}
                    res = await client.post(url, json=data)

                if res.status_code == 200:
                    return True, "Mensagem enviada com sucesso ao Telegram"
                else:
                    return False, f"Erro Telegram HTTP {res.status_code}: {res.text}"
        except Exception as e:
            return False, f"Exceção Telegram: {str(e)}"

    async def send_whatsapp(self, text: str, custom_target: str = None, image_path: str = None) -> tuple[bool, str]:
        wa = self.config.whatsapp
        if not wa.get("enabled") or not wa.get("api_url"):
            return False, "WhatsApp não habilitado ou URL da API ausente"

        provider = wa.get("provider", "evolution")
        api_url = wa.get("api_url", "").rstrip("/")
        api_key = wa.get("api_key", "").strip()
        instance = wa.get("instance_name", "cftv").strip()
        
        target = (custom_target or wa.get("target_number", "")).strip()
        if "@g.us" not in target:
            target = target.replace("+", "").replace(" ", "")

        if not target:
            return False, "Número ou Grupo de WhatsApp destinatário não informado"

        headers = {}
        if api_key:
            headers["apikey"] = api_key
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if provider == "evolution":
                    endpoint = f"{api_url}/message/sendText/{instance}"
                    payload = {
                        "number": target,
                        "options": {"delay": 1200, "presence": "composing"},
                        "textMessage": {"text": text}
                    }
                    res = await client.post(endpoint, json=payload, headers=headers)
                    if res.status_code in [200, 201]:
                        return True, f"Mensagem enviada via Evolution para {target}"
                    return False, f"Erro Evolution API HTTP {res.status_code}: {res.text}"

                elif provider == "zapi":
                    endpoint = f"{api_url}/instances/{instance}/token/{api_key}/send-text"
                    payload = {"phone": target, "message": text}
                    res = await client.post(endpoint, json=payload)
                    if res.status_code in [200, 201]:
                        return True, f"Mensagem enviada via Z-API para {target}"
                    return False, f"Erro Z-API HTTP {res.status_code}: {res.text}"

                elif provider == "webhook":
                    payload = {"number": target, "message": text, "timestamp": datetime.now().isoformat()}
                    res = await client.post(api_url, json=payload, headers=headers)
                    if res.status_code in [200, 201, 204]:
                        return True, "Webhook disparado com sucesso"
                    return False, f"Erro Webhook HTTP {res.status_code}: {res.text}"

                return False, f"Provedor '{provider}' não suportado"
        except Exception as e:
            return False, f"Exceção WhatsApp: {str(e)}"

    def alert_camera_down(self, camera: dict, failed_attempts: int, client_info: dict = None):
        cam_id = camera.get("id")
        if self.should_suppress_flood(f"cam_down_{cam_id}"):
            logger.info(f"[Anti-Flood] Alerta de queda da câmera {camera.get('name')} suprimido.")
            return

        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        client_name = (client_info.get("name") if client_info else None) or camera.get("client_name") or "Geral"
        contact_name = (client_info.get("contact_name") if client_info else None) or "Cliente"

        context = {
            "client_name": client_name,
            "contact_name": contact_name,
            "camera_name": camera.get("name", "Câmera"),
            "camera_ip": camera.get("ip", "0.0.0.0"),
            "camera_port": camera.get("port", 554),
            "nvr_name": camera.get("nvr", "N/A"),
            "channel": camera.get("channel", 1),
            "failures": failed_attempts,
            "timestamp": timestamp
        }

        noc_template = self.config.templates.get("noc_camera_down", "")
        noc_msg = format_template(noc_template, context)
        logger.warning(f"[{client_name}] CÂMERA OFFLINE: {camera['name']} ({camera['ip']})")

        image_path = os.path.join(SNAPSHOT_DIR, f"{cam_id}.jpg")

        _safe_schedule_task(EVENT_BUS.publish("CAMERA_DOWN", camera, failed_attempts, client_info, noc_msg))
        _safe_schedule_task(self.send_telegram(noc_msg, image_path))
        _safe_schedule_task(self.send_whatsapp(noc_msg, image_path=image_path))

        if client_info and client_info.get("notify_client", True) and client_info.get("whatsapp"):
            client_template = self.config.templates.get("client_camera_down", "")
            if client_template:
                client_msg = format_template(client_template, context)
                _safe_schedule_task(self.send_whatsapp(client_msg, custom_target=client_info.get("whatsapp")))

    def alert_camera_recovered(self, camera: dict, client_info: dict = None):
        cam_id = camera.get("id")
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        client_name = (client_info.get("name") if client_info else None) or camera.get("client_name") or "Geral"
        contact_name = (client_info.get("contact_name") if client_info else None) or "Cliente"

        context = {
            "client_name": client_name,
            "contact_name": contact_name,
            "camera_name": camera.get("name", "Câmera"),
            "camera_ip": camera.get("ip", "0.0.0.0"),
            "nvr_name": camera.get("nvr", "N/A"),
            "channel": camera.get("channel", 1),
            "timestamp": timestamp
        }

        noc_template = self.config.templates.get("noc_camera_recovered", "")
        noc_msg = format_template(noc_template, context)
        logger.info(f"[{client_name}] CÂMERA ONLINE: {camera['name']} ({camera['ip']})")

        image_path = os.path.join(SNAPSHOT_DIR, f"{cam_id}.jpg")

        _safe_schedule_task(EVENT_BUS.publish("CAMERA_RECOVERED", camera, client_info, noc_msg))
        _safe_schedule_task(self.send_telegram(noc_msg, image_path))
        _safe_schedule_task(self.send_whatsapp(noc_msg, image_path=image_path))

        if client_info and client_info.get("notify_client", True) and client_info.get("whatsapp"):
            client_template = self.config.templates.get("client_camera_recovered", "")
            if client_template:
                client_msg = format_template(client_template, context)
                _safe_schedule_task(self.send_whatsapp(client_msg, custom_target=client_info.get("whatsapp")))

    def alert_nvr_down(self, nvr_name: str, dvr_ip: str, total_channels: int, offline_count: int, client_info: dict = None):
        device_key = f"nvr_down_{nvr_name}"
        if self.should_suppress_flood(device_key):
            return

        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        client_name = (client_info.get("name") if client_info else None) or "Geral"
        contact_name = (client_info.get("contact_name") if client_info else None) or "Cliente"

        context = {
            "client_name": client_name,
            "contact_name": contact_name,
            "nvr_name": nvr_name,
            "camera_ip": dvr_ip,
            "total_channels": total_channels,
            "offline_count": offline_count,
            "timestamp": timestamp
        }

        noc_template = self.config.templates.get("noc_nvr_down", "")
        noc_msg = format_template(noc_template, context)
        logger.critical(f"[{client_name}] GRAVADOR OFFLINE: {nvr_name} ({dvr_ip})")

        _safe_schedule_task(EVENT_BUS.publish("NVR_DOWN", nvr_name, dvr_ip, total_channels, offline_count, client_info, noc_msg))
        _safe_schedule_task(self.send_telegram(noc_msg))
        _safe_schedule_task(self.send_whatsapp(noc_msg))

        if client_info and client_info.get("notify_client", True) and client_info.get("whatsapp"):
            client_template = self.config.templates.get("client_nvr_down", "")
            if client_template:
                client_msg = format_template(client_template, context)
                _safe_schedule_task(self.send_whatsapp(client_msg, custom_target=client_info.get("whatsapp")))

    def alert_nvr_recovered(self, nvr_name: str, dvr_ip: str, total_channels: int, client_info: dict = None):
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        client_name = (client_info.get("name") if client_info else None) or "Geral"
        contact_name = (client_info.get("contact_name") if client_info else None) or "Cliente"

        context = {
            "client_name": client_name,
            "contact_name": contact_name,
            "nvr_name": nvr_name,
            "camera_ip": dvr_ip,
            "total_channels": total_channels,
            "timestamp": timestamp
        }

        noc_template = self.config.templates.get("noc_nvr_recovered", "")
        noc_msg = format_template(noc_template, context)
        logger.info(f"[{client_name}] GRAVADOR RESTABELECIDO: {nvr_name} ({dvr_ip})")

        _safe_schedule_task(EVENT_BUS.publish("NVR_RECOVERED", nvr_name, dvr_ip, total_channels, client_info, noc_msg))
        _safe_schedule_task(self.send_telegram(noc_msg))
        _safe_schedule_task(self.send_whatsapp(noc_msg))

        if client_info and client_info.get("notify_client", True) and client_info.get("whatsapp"):
            client_template = self.config.templates.get("client_nvr_recovered", "")
            if client_template:
                client_msg = format_template(client_template, context)
                _safe_schedule_task(self.send_whatsapp(client_msg, custom_target=client_info.get("whatsapp")))

    async def test_notification(self, channel: str, target_number: str = None) -> tuple[bool, str]:
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        msg = f"🛡️ *[CFTV Sentinel]* Teste de Notificação!\n\nCanal: *{channel.upper()}*\nHorário: {now_str}\nStatus: Operando Normalmente ✅"
        if channel.lower() == "telegram":
            return await self.send_telegram(msg)
        elif channel.lower() == "whatsapp":
            return await self.send_whatsapp(msg, custom_target=target_number)
        return False, "Canal desconhecido"

Notifier = NotificationService()
