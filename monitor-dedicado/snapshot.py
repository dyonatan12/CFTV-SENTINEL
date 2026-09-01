import os
import asyncio
import httpx
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# Semáforo global para requisições de snapshot (máximo 6 simultâneas para não estressar os DVRs)
SNAPSHOT_SEMAPHORE = asyncio.Semaphore(4)

def get_rtsp_url(camera_data: dict) -> str:
    ip = camera_data.get("ip", "127.0.0.1")
    port = camera_data.get("rtsp_port") or camera_data.get("port") or 554
    if port in [37777, 80]:
        port = 554

    username = camera_data.get("username", "admin")
    password = camera_data.get("password", "")
    channel = camera_data.get("channel", 1)

    auth_str = f"{username}:{password}@" if (username or password) else ""
    return f"rtsp://{auth_str}{ip}:{port}/cam/realmonitor?channel={channel}&subtype=1"

def generate_mock_snapshot(camera_data: dict, output_path: str):
    width, height = 480, 270
    bg_color = (25, 30, 40)
    
    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    draw.rectangle([10, 10, width - 10, height - 10], outline=(45, 55, 75), width=2)
    draw.line([width//2 - 15, height//2, width//2 + 15, height//2], fill=(60, 80, 110), width=1)
    draw.line([width//2, height//2 - 15, width//2, height//2 + 15], fill=(60, 80, 110), width=1)
    
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    name = camera_data.get("name", "Câmera")
    ip = camera_data.get("ip", "0.0.0.0")
    nvr = camera_data.get("nvr", "NVR")
    channel = camera_data.get("channel", 1)

    draw.text((20, 20), f"CAM: {name.upper()}", fill=(220, 220, 220))
    draw.text((20, 40), f"IP: {ip} | {nvr} CH{channel}", fill=(160, 170, 180))
    draw.text((20, height - 35), f"REC ● {now_str}", fill=(240, 80, 80))
    draw.text((width - 120, height - 35), "INTELBRAS", fill=(100, 180, 255))
    
    temp_path = f"{output_path}.tmp"
    img.save(temp_path, "JPEG", quality=85)
    try:
        os.replace(temp_path, output_path)
    except Exception:
        pass

def capture_frame_from_rtsp(rtsp_url: str, output_path: str) -> bool:
    if not HAS_OPENCV:
        return False
    try:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;3000000"
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        if not cap.isOpened():
            return False

        ret, frame = cap.read()
        cap.release()

        if ret and frame is not None and frame.size > 0:
            h, w = frame.shape[:2]
            if w > 640:
                scale = 640 / w
                frame = cv2.resize(frame, (640, int(h * scale)))
            
            success, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if success:
                temp_path = f"{output_path}.tmp"
                with open(temp_path, "wb") as f:
                    f.write(encoded.tobytes())
                os.replace(temp_path, output_path)
                return True
        return False
    except Exception:
        return False

async def capture_snapshot(camera_data: dict, is_mock: bool = False) -> tuple[bool, str]:
    cam_id = camera_data.get("id")
    output_filename = f"{cam_id}.jpg"
    output_path = os.path.join(SNAPSHOT_DIR, output_filename)
    
    if is_mock or not camera_data.get("username"):
        generate_mock_snapshot(camera_data, output_path)
        return True, f"/snapshots/{output_filename}"

    ip = camera_data.get("ip")
    http_port = camera_data.get("http_port", 80)
    username = camera_data.get("username", "admin")
    password = camera_data.get("password", "")
    channel = camera_data.get("channel", 1)

    async with SNAPSHOT_SEMAPHORE:
        # 1. TENTA VIA HTTP CGI INTELBRAS (timeout equilibrado de 3.5s)
        snapshot_url = camera_data.get("snapshot_url")
        if not snapshot_url:
            snapshot_url = f"http://{ip}:{http_port}/cgi-bin/snapshot.cgi?channel={channel}"

        try:
            auth = httpx.DigestAuth(username, password) if password else None
            async with httpx.AsyncClient(timeout=3.5, verify=False) as client:
                resp = await client.get(snapshot_url, auth=auth)
                if resp.status_code == 401 and password:
                    resp = await client.get(snapshot_url, auth=httpx.BasicAuth(username, password))

                if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                    if len(resp.content) > 1000: # Foto válida (mais de 1KB)
                        temp_path = f"{output_path}.tmp"
                        with open(temp_path, "wb") as f:
                            f.write(resp.content)
                        os.replace(temp_path, output_path)
                        return True, f"/snapshots/{output_filename}"
                elif resp.status_code == 400:
                    # 400 no NVR Intelbras significa especificamente "Host não encontrado / Sem Sinal"
                    return False, "Câmera desconectada do NVR (Host não encontrado)"
        except Exception:
            pass

        # 2. TENTA VIA FLUXO RTSP SE HTTP FALHAR (rápido com OpenCV)
        if HAS_OPENCV:
            try:
                rtsp_url = get_rtsp_url(camera_data)
                success = await asyncio.wait_for(
                    asyncio.to_thread(capture_frame_from_rtsp, rtsp_url, output_path),
                    timeout=3.0
                )
                if success:
                    return True, f"/snapshots/{output_filename}"
            except Exception:
                pass

    # Se já temos uma foto anterior salva no disco, preserva ela
    if os.path.exists(output_path):
        return False, f"/snapshots/{output_filename}"

    generate_mock_snapshot(camera_data, output_path)
    return False, "Canal inacessível"
