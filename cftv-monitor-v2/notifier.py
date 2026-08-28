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
    result = template_str
    for k, v in context.items():
        result = result.replace(f"{{{k}}}", str(v if v is not None else ""))
    return result

def convert_to_html(text: str) -> str:
    import re
    text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    return text

LAST_ALERT_TIMESTAMPS = {}
ALERT_COOLDOWN_SECONDS = 600  # 10 minutos de intervalo mínimo por câmera/evento

class Notifier:
    """
    Central de Despacho Duplo (v2.0):
    1. NOC Interno (Grupo do Telegram / WhatsApp da Central com detalhes técnicos)
    2. Cliente Específico (WhatsApp pessoal do Dono/Gerente da empresa com mensagem amigável)
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
    async def send_whatsapp(text: str, custom_target: str = None, image_path: str = None) -> tuple[bool, str]:
        wa = CONFIG.whatsapp
        if not wa.get("enabled") or not wa.get("api_url"):
            return False, "WhatsApp não habilitado ou URL da API ausente"

        provider = wa.get("provider", "evolution")
        api_url = wa.get("api_url", "").rstrip("/")
        api_key = wa.get("api_key", "").strip()
        instance = wa.get("instance_name", "cftv").strip()
        
        # Se for passado um número de cliente específico, usa ele. Senão usa o padrão da central.
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

    @classmethod
    def alert_camera_down(cls, camera: dict, failed_attempts: int, client_info: dict = None):
        cam_id = camera.get("id")
        if cls.should_suppress_flood(f"cam_down_{cam_id}"):
            logging.info(f"[Anti-Flood] Alerta de queda da câmera {camera.get('name')} suprimido (cooldown ativo).")
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

        # 1. Alerta Interno (NOC)
        noc_template = CONFIG.templates.get("noc_camera_down", "")
        noc_msg = format_template(noc_template, context)
        print(f"\033[91m\n{noc_msg}\n\033[0m")
        logging.warning(f"[{client_name}] CÂMERA OFFLINE: {camera['name']} ({camera['ip']})")

        image_path = os.path.join(os.path.dirname(__file__), "snapshots", f"{cam_id}.jpg")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Disparo NOC (Telegram + WhatsApp Geral)
                asyncio.create_task(cls.send_telegram(noc_msg, image_path))
                asyncio.create_task(cls.send_whatsapp(noc_msg, image_path=image_path))

                # 2. Alerta do Cliente (se habilitado no cadastro do cliente)
                if client_info and client_info.get("notify_client") and client_info.get("whatsapp"):
                    client_template = CONFIG.templates.get("client_camera_down", "")
                    client_msg = format_template(client_template, context)
                    asyncio.create_task(cls.send_whatsapp(client_msg, custom_target=client_info["whatsapp"]))
        except Exception as e:
            print(f"[ERRO ALERTA CAMERA]: {e}")

    @classmethod
    def alert_camera_recovered(cls, camera: dict, client_info: dict = None):
        cam_id = camera.get("id")
        if cls.should_suppress_flood(f"cam_rec_{cam_id}"):
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
            "timestamp": timestamp
        }

        # 1. NOC Interno
        noc_template = CONFIG.templates.get("noc_camera_recovered", "")
        noc_msg = format_template(noc_template, context)
        print(f"\033[92m\n{noc_msg}\n\033[0m")
        logging.info(f"[{client_name}] CÂMERA ONLINE: {camera['name']}")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(cls.send_telegram(noc_msg))
                asyncio.create_task(cls.send_whatsapp(noc_msg))

                # 2. Cliente
                if client_info and client_info.get("notify_client") and client_info.get("whatsapp"):
                    client_template = CONFIG.templates.get("client_camera_recovered", "")
                    client_msg = format_template(client_template, context)
                    asyncio.create_task(cls.send_whatsapp(client_msg, custom_target=client_info["whatsapp"]))
        except Exception as e:
            print(f"[ERRO RECUPERAÇÃO CAMERA]: {e}")

    @classmethod
    def alert_nvr_down(cls, nvr_name: str, dvr_ip: str, total_channels: int, offline_count: int, client_info: dict = None):
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

        # 1. NOC Interno
        noc_template = CONFIG.templates.get("noc_nvr_down", "")
        noc_msg = format_template(noc_template, context)
        print(f"\033[91m\n{'='*50}\n{noc_msg}\n{'='*50}\n\033[0m")
        logging.warning(f"[{client_name}] GRAVADOR OFFLINE: {nvr_name} ({dvr_ip})")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(cls.send_telegram(noc_msg))
                asyncio.create_task(cls.send_whatsapp(noc_msg))

                # 2. Cliente
                if client_info and client_info.get("notify_client") and client_info.get("whatsapp"):
                    client_template = CONFIG.templates.get("client_nvr_down", "")
                    client_msg = format_template(client_template, context)
                    asyncio.create_task(cls.send_whatsapp(client_msg, custom_target=client_info["whatsapp"]))
        except Exception as e:
            print(f"[ERRO ALERTA NVR]: {e}")

    @classmethod
    def alert_nvr_recovered(cls, nvr_name: str, dvr_ip: str, total_channels: int, client_info: dict = None):
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

        # 1. NOC Interno
        noc_template = CONFIG.templates.get("noc_nvr_recovered", "")
        noc_msg = format_template(noc_template, context)
        print(f"\033[92m\n{'='*50}\n{noc_msg}\n{'='*50}\n\033[0m")
        logging.info(f"[{client_name}] GRAVADOR RESTABELECIDO: {nvr_name}")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(cls.send_telegram(noc_msg))
                asyncio.create_task(cls.send_whatsapp(noc_msg))

                # 2. Cliente
                if client_info and client_info.get("notify_client") and client_info.get("whatsapp"):
                    client_template = CONFIG.templates.get("client_nvr_recovered", "")
                    client_msg = format_template(client_template, context)
                    asyncio.create_task(cls.send_whatsapp(client_msg, custom_target=client_info["whatsapp"]))
        except Exception as e:
            print(f"[ERRO RECUPERAÇÃO NVR]: {e}")

    @classmethod
    async def test_notification(cls, channel: str, target_number: str = None) -> tuple[bool, str]:
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        text = f"🧪 *TESTE DE NOTIFICAÇÃO CFTV MONITOR v2.0*\n\nSe você está lendo isso, a integração com o *{channel.upper()}* está funcionando com sucesso!\n\n🕒 Horário: {timestamp}"

        if channel == "telegram":
            return await cls.send_telegram(text)
        elif channel == "whatsapp":
            return await cls.send_whatsapp(text, custom_target=target_number)
        return False, "Canal desconhecido"
