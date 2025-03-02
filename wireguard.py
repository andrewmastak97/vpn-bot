import os
import subprocess
from typing import Tuple
import base64
import json
from pathlib import Path

def generate_keypair() -> Tuple[str, str]:
    """Генерирует пару ключей WireGuard"""
    private_key = subprocess.check_output(["wg", "genkey"]).decode("utf-8").strip()
    public_key = subprocess.check_output(["wg", "pubkey"], input=private_key.encode()).decode("utf-8").strip()
    return private_key, public_key

def generate_config(
    private_key: str,
    server_public_key: str,
    server_endpoint: str,
    client_ip: str,
    dns_servers: str
) -> str:
    """Генерирует конфигурацию WireGuard для клиента"""
    config = f"""[Interface]
PrivateKey = {private_key}
Address = {client_ip}/32
DNS = {dns_servers}

[Peer]
PublicKey = {server_public_key}
AllowedIPs = 0.0.0.0/0
Endpoint = {server_endpoint}
PersistentKeepalive = 25"""
    return config

def generate_qr_config(config: str) -> str:
    """Генерирует QR-код конфигурации для мобильных устройств"""
    config_bytes = config.encode('utf-8')
    config_base64 = base64.b64encode(config_bytes).decode('utf-8')
    return f"wireguard://{config_base64}"

def get_next_ip(last_ip: str = "10.0.0.0") -> str:
    """Получает следующий доступный IP-адрес"""
    ip_parts = list(map(int, last_ip.split('.')))
    ip_parts[3] += 1
    if ip_parts[3] > 254:
        ip_parts[3] = 0
        ip_parts[2] += 1
    return '.'.join(map(str, ip_parts))

async def create_client_config(user_id: int) -> Tuple[str, str, str]:
    """Создает конфигурацию для нового клиента"""
    private_key, public_key = generate_keypair()
    
    # В реальном приложении эти значения должны браться из конфигурации
    server_public_key = os.getenv("WG_SERVER_PUBLIC_KEY")
    server_endpoint = os.getenv("WG_SERVER_ENDPOINT")
    dns_servers = os.getenv("WG_DNS")
    
    # В реальном приложении IP должен выбираться из пула доступных адресов
    client_ip = get_next_ip()
    
    config = generate_config(
        private_key=private_key,
        server_public_key=server_public_key,
        server_endpoint=server_endpoint,
        client_ip=client_ip,
        dns_servers=dns_servers
    )
    
    qr_config = generate_qr_config(config)
    
    return private_key, public_key, config, qr_config 