import os
import sys
import logging
import httpx
import asyncio
from datetime import datetime
from config import CONFIG

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    filename=CONFIG.log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

def format_template(template_str: str, context: dict) -> str:
    """Substitui tags {variavel} no template de forma segura"""
    result = template_str
    for k, v in context.items():
        result = result.replace(f"{{{k}}}", str(v))
    return result

def convert_to_html(text: str) -> str:
    """Converte markdown simples (*negrito*, `codigo`) para tags HTML do Telegram"""
    import re
    # *texto* -> <b>texto</b>
    text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)
    # `texto` -> <code>texto</code>
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    return text

LAST_ALERT_TIMESTAMPS = {}
ALERT_COOLDOWN_SECONDS = 600  # 10 minutos de intervalo mínimo por câmera/evento

class Notifier:
    """
    Central de Despacho de Notificações com Templates Customizáveis:
    - Quedas individuais de câmeras
    - Quedas coletivas de Gravador (DVR/NVD)
    - Suporte a Telegram e WhatsApp
    """

    @staticmethod
    def should_suppress_flood(device_key: str) -> bool:
        now = datetime.now().timestamp()
        last = LAST_ALERT_TIMESTAMPS.get(device_key, 0)
        if (now - last) < ALERT_COOLDOWN_SECONDS:
            return True
        LAST_ALERT_TIMESTAMPS[device_key] = now
        return False

    @staticmethod
    async def send_telegram(text: str, image_path: str = None) -> tuple[bool, str]:
        tg = CONFIG.telegram
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

    @staticmethod
    async def send_whatsapp(text: str, image_path: str = None) -> tuple[bool, str]:
        wa = CONFIG.whatsapp
        if not wa.get("enabled") or not wa.get("api_url"):
            return False, "WhatsApp não habilitado ou URL da API ausente"

        provider = wa.get("provider", "evolution")
        api_url = wa.get("api_url", "").rstrip("/")
        api_key = wa.get("api_key", "").strip()
        instance = wa.get("instance_name", "cftv").strip()
        target = wa.get("target_number", "").strip()
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
                        return True, "Mensagem enviada via Evolution API"
                    return False, f"Erro Evolution API HTTP {res.status_code}: {res.text}"

                elif provider == "zapi":
                    endpoint = f"{api_url}/instances/{instance}/token/{api_key}/send-text"
                    payload = {"phone": target, "message": text}
                    res = await client.post(endpoint, json=payload)
                    if res.status_code in [200, 201]:
                        return True, "Mensagem enviada via Z-API"
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

    @classmethod
    def alert_camera_down(cls, camera: dict, failed_attempts: int):
        cam_id = camera.get("id")
        if cls.should_suppress_flood(f"cam_down_{cam_id}"):
            logging.info(f"[Anti-Flood] Queda da câmera {camera.get('name')} suprimida (cooldown ativo).")
            return

        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        context = {
            "camera_name": camera.get("name", "Câmera"),
            "camera_ip": camera.get("ip", "0.0.0.0"),
            "camera_port": camera.get("port", 554),
            "nvr_name": camera.get("nvr", "N/A"),
            "channel": camera.get("channel", 1),
            "failures": failed_attempts,
            "timestamp": timestamp
        }

        template = CONFIG.templates.get("camera_down", "")
        message = format_template(template, context)

        print(f"\033[91m\n{message}\n\033[0m")
        logging.warning(f"CÂMERA OFFLINE: {camera['name']} ({camera['ip']})")

        image_path = os.path.join(os.path.dirname(__file__), "snapshots", f"{cam_id}.jpg")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(cls.send_telegram(message, image_path))
                asyncio.create_task(cls.send_whatsapp(message, image_path))
        except Exception as e:
            print(f"[ERRO ALERTA CAMERA]: {e}")

    @classmethod
    def alert_camera_recovered(cls, camera: dict):
        cam_id = camera.get("id")
        if cls.should_suppress_flood(f"cam_rec_{cam_id}"):
            return

        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        context = {
            "camera_name": camera.get("name", "Câmera"),
            "camera_ip": camera.get("ip", "0.0.0.0"),
            "camera_port": camera.get("port", 554),
            "nvr_name": camera.get("nvr", "N/A"),
            "channel": camera.get("channel", 1),
            "timestamp": timestamp
        }

        template = CONFIG.templates.get("camera_recovered", "")
        message = format_template(template, context)

        print(f"\033[92m\n{message}\n\033[0m")
        logging.info(f"CÂMERA ONLINE: {camera['name']}")

        cam_id = camera.get("id")
        image_path = os.path.join(os.path.dirname(__file__), "snapshots", f"{cam_id}.jpg")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(cls.send_telegram(message, image_path))
                asyncio.create_task(cls.send_whatsapp(message, image_path))
        except Exception as e:
            print(f"[ERRO RECUPERAÇÃO CAMERA]: {e}")

    @classmethod
    def alert_nvr_down(cls, nvr_name: str, dvr_ip: str, total_channels: int, offline_count: int):
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        context = {
            "nvr_name": nvr_name,
            "camera_ip": dvr_ip,
            "total_channels": total_channels,
            "offline_count": offline_count,
            "timestamp": timestamp
        }

        template = CONFIG.templates.get("nvr_down", "")
        message = format_template(template, context)

        print(f"\033[91m\n{'='*50}\n{message}\n{'='*50}\n\033[0m")
        logging.warning(f"GRAVADOR OFFLINE: {nvr_name} ({dvr_ip}) - {offline_count}/{total_channels} canais caídos")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(cls.send_telegram(message))
                asyncio.create_task(cls.send_whatsapp(message))
        except Exception as e:
            print(f"[ERRO ALERTA NVR]: {e}")

    @classmethod
    def alert_nvr_recovered(cls, nvr_name: str, dvr_ip: str, total_channels: int):
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        context = {
            "nvr_name": nvr_name,
            "camera_ip": dvr_ip,
            "total_channels": total_channels,
            "timestamp": timestamp
        }

        template = CONFIG.templates.get("nvr_recovered", "")
        message = format_template(template, context)

        print(f"\033[92m\n{'='*50}\n{message}\n{'='*50}\n\033[0m")
        logging.info(f"GRAVADOR RESTABELECIDO: {nvr_name} ({dvr_ip})")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(cls.send_telegram(message))
                asyncio.create_task(cls.send_whatsapp(message))
        except Exception as e:
            print(f"[ERRO RECUPERAÇÃO NVR]: {e}")

    @classmethod
    async def test_notification(cls, channel: str) -> tuple[bool, str]:
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        text = f"🧪 *TESTE DE NOTIFICAÇÃO CFTV MONITOR*\n\nSe você está lendo isso, a integração com o *{channel.upper()}* está funcionando com sucesso!\n\n🕒 Horário: {timestamp}"

        if channel == "telegram":
            return await cls.send_telegram(text)
        elif channel == "whatsapp":
            return await cls.send_whatsapp(text)
        return False, "Canal desconhecido"
