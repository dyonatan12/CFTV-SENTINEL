import os
import base64
import logging

logger = logging.getLogger("cftv.security")

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

ENCRYPTION_PREFIX = "enc::"

def get_encryption_key() -> str:
    return os.getenv("ENCRYPTION_KEY", "").strip()

def encrypt_secret(plain_text: str) -> str:
    """
    Encripta um segredo usando AES-256 (Fernet) se ENCRYPTION_KEY estiver definida.
    Se não houver chave ou já estiver encriptado, retorna o valor apropriado.
    """
    if not plain_text:
        return ""
    if plain_text.startswith(ENCRYPTION_PREFIX):
        return plain_text
    
    key = get_encryption_key()
    if not key or not HAS_CRYPTOGRAPHY:
        return plain_text
    
    try:
        f = Fernet(key.encode() if isinstance(key, str) else key)
        encrypted_bytes = f.encrypt(plain_text.encode("utf-8"))
        return f"{ENCRYPTION_PREFIX}{encrypted_bytes.decode('utf-8')}"
    except Exception as e:
        logger.warning(f"Falha ao encriptar segredo: {e}")
        return plain_text

def decrypt_secret(cipher_text: str) -> str:
    """
    Decripta um segredo encriptado com o prefixo 'enc::'.
    Se não estiver encriptado ou a chave for inválida, retorna o texto original.
    """
    if not cipher_text:
        return ""
    if not cipher_text.startswith(ENCRYPTION_PREFIX):
        return cipher_text
    
    key = get_encryption_key()
    if not key or not HAS_CRYPTOGRAPHY:
        return cipher_text
    
    raw_payload = cipher_text[len(ENCRYPTION_PREFIX):]
    try:
        f = Fernet(key.encode() if isinstance(key, str) else key)
        decrypted_bytes = f.decrypt(raw_payload.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except Exception as e:
        logger.error(f"Falha ao decriptar segredo: {e}")
        return cipher_text

def sanitize_device_for_api(device: dict) -> dict:
    """
    Remove ou ofusca campos confidenciais antes de retornar na API.
    """
    sanitized = dict(device)
    raw_pass = sanitized.get("password", "")
    sanitized["has_password"] = bool(raw_pass)
    if "password" in sanitized:
        sanitized["password"] = "********" if raw_pass else ""
    return sanitized
