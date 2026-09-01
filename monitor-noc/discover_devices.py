import asyncio
import socket
import json
import ipaddress
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def check_port(ip, port, timeout=1.0):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return port
    except Exception:
        return None

async def scan_ip(ip, ports):
    tasks = [check_port(str(ip), p) for p in ports]
    results = await asyncio.gather(*tasks)
    open_ports = [p for p in results if p is not None]
    
    if open_ports:
        logging.info(f"[ENCONTRADO] Dispositivo em {ip} - Portas: {open_ports}")
        return {"ip": str(ip), "ports": open_ports}
    return None

async def discover_devices(network_cidr="192.168.0.0/24", ports=[80, 554, 37777, 8000, 8999]):
    logging.info(f"Iniciando varredura na rede {network_cidr} nas portas {ports}...")
    network = ipaddress.ip_network(network_cidr, strict=False)
    
    tasks = []
    # Limita o número de tarefas simultâneas para não estourar os sockets
    sem = asyncio.Semaphore(100)
    
    async def bounded_scan(ip):
        async with sem:
            return await scan_ip(ip, ports)

    for ip in network.hosts():
        tasks.append(bounded_scan(ip))
        
    results = await asyncio.gather(*tasks)
    found = [r for r in results if r is not None]
    
    logging.info(f"Varredura concluída. {len(found)} dispositivos de CFTV/DVR/NVR encontrados.")
    
    # Salva os resultados
    with open("discovered_devices.json", "w") as f:
        json.dump(found, f, indent=4)
        
    return found

if __name__ == "__main__":
    # Coloque a faixa de IP da sua rede aqui
    rede_alvo = input("Digite a rede para buscar (ex: 192.168.1.0/24): ")
    if not rede_alvo:
        rede_alvo = "192.168.1.0/24"
        
    asyncio.run(discover_devices(network_cidr=rede_alvo))
