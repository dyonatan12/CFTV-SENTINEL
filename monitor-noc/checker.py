import asyncio
import time
from typing import Tuple

async def check_camera_tcp(ip: str, port: int, timeout: float = 2.5) -> Tuple[bool, float]:
    """
    Tenta abrir conexão TCP no IP e porta especificados com fallback inteligente.
    """
    start_time = time.perf_counter()
    ports_to_try = [port]
    if port == 554:
        ports_to_try.extend([37777, 80])
    elif port == 37777:
        ports_to_try.extend([554, 80])
    elif port == 80:
        ports_to_try.extend([554, 37777])

    for p in ports_to_try:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, p),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return True, latency_ms
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            continue

    return False, 0.0

async def check_camera_health(camera_data: dict, timeout: float = 3.5, is_mock: bool = False) -> Tuple[bool, float]:
    """
    Verificação Híbrida:
    1. Se for canal de DVR com credenciais: faz a captura real do frame (CGI HTTP ou RTSP via OpenCV).
       Se a captura der certo -> Canal ONLINE com Imagem Real salva no disco.
       Se a captura der erro (ex: HTTP 400 'host não encontrado' no NVR) -> Canal OFFLINE.
    2. Se for câmera IP avulsa sem credenciais: teste TCP.
    """
    if is_mock:
        return await mock_check_camera(camera_data.get("id"))

    channel = camera_data.get("channel", 0)
    has_credentials = bool(camera_data.get("username"))
    is_nvr_channel = (channel >= 1 and camera_data.get("nvr") and camera_data.get("nvr") != "N/A")

    if is_nvr_channel and has_credentials:
        from snapshot import capture_snapshot
        start_time = time.perf_counter()
        success, _ = await capture_snapshot(camera_data, is_mock=False)
        latency_ms = (time.perf_counter() - start_time) * 1000.0
        return success, latency_ms

    # Câmeras IP avulsas sem NVR / sem credenciais de canal
    ip = camera_data.get("ip")
    port = camera_data.get("port", 554)
    return await check_camera_tcp(ip, port, timeout=timeout)

async def mock_check_camera(camera_id: str, failure_rate: float = 0.1) -> Tuple[bool, float]:
    await asyncio.sleep(0.05)
    if camera_id == "cam-004":
        return False, 0.0
    return True, 12.5
