import asyncio
import time
import json
import argparse
import sys
import os
from datetime import datetime

# Garante compatibilidade UTF-8 no console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import CONFIG
from checker import check_camera_tcp, mock_check_camera
from tracker import DeviceTracker, CameraStatus

def load_cameras(file_path: str) -> list[dict]:
    if not os.path.exists(file_path):
        print(f"\033[91m[ERRO] Arquivo de inventário não encontrado: {file_path}\033[0m")
        sys.exit(1)
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_128_dummy_cameras():
    """Gera um arquivo de exemplo com 128 câmeras distribuídas em 6 NVDs/iNVDs"""
    cams = []
    nvrs = ["NVD-01 (Portaria)", "NVD-02 (Estoque)", "NVD-03 (Loja)", "iNVD-01 (Galpão A)", "iNVD-02 (Galpão B)", "iNVD-03 (Perímetro)"]
    
    # 6 NVRs
    for i, nvr_name in enumerate(nvrs, 1):
        cams.append({
            "id": f"nvr-{i:02d}",
            "name": f"Gravador Intelbras {nvr_name}",
            "ip": f"192.168.1.{200+i}",
            "port": 37777,
            "nvr": "N/A",
            "channel": 0
        })

    # 128 Câmeras
    for i in range(1, 129):
        nvr_idx = (i - 1) % len(nvrs)
        channel = ((i - 1) // len(nvrs)) + 1
        cams.append({
            "id": f"cam-{i:03d}",
            "name": f"Câmera {i:03d} - Setor {chr(65 + (i % 6))}",
            "ip": f"192.168.2.{i}",
            "port": 554,
            "nvr": nvrs[nvr_idx],
            "channel": channel
        })

    out_file = os.path.join(os.path.dirname(__file__), "cameras_128.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(cams, f, indent=2, ensure_ascii=False)
    print(f"\033[92m[OK] Arquivo gerado com sucesso: {out_file} (128 câmeras + 6 NVRs)\033[0m")

async def scan_single_device(sem: asyncio.Semaphore, device_data: dict, is_mock: bool):
    async with sem:
        if is_mock:
            is_success, latency = await mock_check_camera(device_data["id"])
        else:
            is_success, latency = await check_camera_tcp(
                ip=device_data["ip"],
                port=device_data.get("port", 554),
                timeout=CONFIG.connection_timeout
            )
        return device_data["id"], is_success, latency

async def run_monitor_loop(cameras: list[dict], is_mock: bool = False):
    tracker = DeviceTracker(
        cameras=cameras,
        failure_threshold=CONFIG.failure_threshold,
        recovery_threshold=CONFIG.recovery_threshold
    )
    
    sem = asyncio.Semaphore(CONFIG.max_concurrent_checks)
    cycle = 1
    
    print("\n" + "="*60)
    print(" 📹 CFTV MONITOR - SISTEMA DE VIGILÂNCIA DE CÂMERAS IP")
    print(f" • Dispositivos monitorados: {len(cameras)}")
    print(f" • Intervalo de checagem:   {CONFIG.check_interval}s")
    print(f" • Tolerância a falhas:      {CONFIG.failure_threshold} ciclos antes de alertar")
    print(f" • Modo de execução:        {'SIMULAÇÃO (MOCK)' if is_mock else 'REDE REAL (TCP 554/37777)'}")
    print("="*60 + "\n")

    try:
        while True:
            start_cycle = time.perf_counter()
            now_str = datetime.now().strftime("%H:%M:%S")
            
            # Dispara checagens de todas as câmeras em paralelo
            tasks = [scan_single_device(sem, cam, is_mock) for cam in cameras]
            results = await asyncio.gather(*tasks)
            
            # Atualiza o estado de cada dispositivo
            for cam_id, is_success, latency in results:
                dev = tracker.get_device(cam_id)
                dev.update_result(is_success, latency)
            
            summary = tracker.get_summary()
            elapsed = time.perf_counter() - start_cycle
            
            # Exibe status compacto do ciclo
            status_line = (
                f"[{now_str}] Ciclo #{cycle:03d} | "
                f"Tempo de varredura: {elapsed:.2f}s | "
                f"\033[92mONLINE: {summary['online']}\033[0m | "
                f"\033[91mOFFLINE: {summary['offline']}\033[0m | "
                f"\033[93mINSTÁVEL: {summary['pending']}\033[0m"
            )
            print(status_line)
            
            cycle += 1
            await asyncio.sleep(CONFIG.check_interval)
            
    except asyncio.CancelledError:
        print("\n\033[93mMonitoramento finalizado.\033[0m")

def main():
    parser = argparse.ArgumentParser(description="CFTV Monitor MVP")
    parser.add_argument("--mock", action="store_true", help="Executa em modo de simulação para testes locais")
    parser.add_argument("--generate-128", action="store_true", help="Gera arquivo de inventário com 128 câmeras de teste")
    parser.add_argument("--file", type=str, default=CONFIG.cameras_file, help="Caminho do arquivo de câmeras JSON")
    
    args = parser.parse_args()
    
    if args.generate_128:
        generate_128_dummy_cameras()
        return

    cameras = load_cameras(args.file)
    try:
        asyncio.run(run_monitor_loop(cameras, is_mock=args.mock))
    except KeyboardInterrupt:
        print("\n[Encerrado pelo usuário]")

if __name__ == "__main__":
    main()
