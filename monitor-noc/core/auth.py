import os
import json
import time
import uuid
import hmac
import hashlib
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models.schemas import (
    LoginRequest,
    TokenResponse,
    ChangePasswordRequest,
    CreateUserRequest
)

logger = logging.getLogger("cftv.auth")

USERS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "users.json")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "default_cftv_sentinel_secret_key_change_in_prod_123456")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

try:
    import jwt
    HAS_PYJWT = True
except ImportError:
    HAS_PYJWT = False

ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"

# --- RATE LIMITER ANTI-BRUTE FORCE ---
class InMemoryRateLimiter:
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.attempts: Dict[str, List[float]] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        timestamps = self.attempts.get(client_ip, [])
        timestamps = [ts for ts in timestamps if now - ts < self.window_seconds]
        if len(timestamps) >= self.max_requests:
            self.attempts[client_ip] = timestamps
            return False
        timestamps.append(now)
        self.attempts[client_ip] = timestamps
        return True

LOGIN_RATE_LIMITER = InMemoryRateLimiter(max_requests=5, window_seconds=60)

# --- PASSWORD HASHING (PBKDF2-HMAC-SHA256) ---
def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return hashed, salt

def verify_password(password: str, hashed: str, salt: str) -> bool:
    check_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(check_hash, hashed)

# --- JWT TOKENS ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": int(expire.timestamp()),
        "iat": int((now - timedelta(seconds=10)).timestamp())
    })
    
    if HAS_PYJWT:
        return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    else:
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps(to_encode).encode()).decode().rstrip("=")
        signature_raw = hmac.new(JWT_SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        signature = base64.urlsafe_b64encode(signature_raw).decode().rstrip("=")
        return f"{header}.{payload}.{signature}"

def decode_access_token(token: str) -> Optional[dict]:
    if HAS_PYJWT:
        try:
            return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM], leeway=10)
        except Exception as e:
            logger.warning(f"Erro ao decodificar token JWT: {e}")
            return None
    else:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header_b64, payload_b64, signature_b64 = parts
            sig_raw = hmac.new(JWT_SECRET_KEY.encode(), f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
            sig_expected = base64.urlsafe_b64encode(sig_raw).decode().rstrip("=")
            if not hmac.compare_digest(signature_b64, sig_expected):
                return None
            padded_payload = payload_b64 + "=" * (-len(payload_b64) % 4)
            payload_data = json.loads(base64.urlsafe_b64decode(padded_payload.encode()).decode())
            if "exp" in payload_data and int(time.time()) > payload_data["exp"]:
                return None
            return payload_data
        except Exception as e:
            logger.warning(f"Erro na validação do token: {e}")
            return None

# --- GERENCIADOR DE USUÁRIOS ---
class UserManager:
    def __init__(self, filepath: str = USERS_FILE):
        self.filepath = filepath
        self.users: List[dict] = []
        self.load_users()

    def load_users(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.users = json.load(f)
            except Exception as e:
                logger.error(f"Erro ao carregar {self.filepath}: {e}")
                self.users = []
        else:
            self.users = []
            self.create_initial_admin()

    def save_users(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.users, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar {self.filepath}: {e}")

    def create_initial_admin(self):
        initial_user = os.getenv("INITIAL_ADMIN_USERNAME", "admin").strip()
        initial_pass = os.getenv("INITIAL_ADMIN_PASSWORD", "help12345").strip()
        initial_name = os.getenv("INITIAL_ADMIN_NAME", "Administrador Central").strip()
        
        pwd_hash, salt = hash_password(initial_pass)
        admin_user = {
            "id": f"usr-{uuid.uuid4().hex[:6]}",
            "username": initial_user,
            "name": initial_name,
            "password_hash": pwd_hash,
            "salt": salt,
            "role": ROLE_ADMIN,
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None
        }
        self.users.append(admin_user)
        self.save_users()
        logger.info(f"🛡️ [SECURITY] Usuário administrador padrão criado: '{initial_user}'")

    def get_by_username(self, username: str) -> Optional[dict]:
        for u in self.users:
            if u.get("username", "").lower() == username.lower():
                return u
        return None

    def get_by_id(self, user_id: str) -> Optional[dict]:
        for u in self.users:
            if u.get("id") == user_id:
                return u
        return None

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        user = self.get_by_username(username)
        if not user or not user.get("active", True):
            return None
        if verify_password(password, user["password_hash"], user["salt"]):
            user["last_login"] = datetime.now(timezone.utc).isoformat()
            self.save_users()
            return user
        return None

    def create_user(self, username: str, password: str, name: str, role: str = ROLE_OPERATOR) -> dict:
        if self.get_by_username(username):
            raise ValueError(f"Usuário '{username}' já existe.")
        if role not in [ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER]:
            raise ValueError(f"Role '{role}' inválida.")
        
        pwd_hash, salt = hash_password(password)
        new_user = {
            "id": f"usr-{uuid.uuid4().hex[:6]}",
            "username": username.strip(),
            "name": name.strip(),
            "password_hash": pwd_hash,
            "salt": salt,
            "role": role,
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None
        }
        self.users.append(new_user)
        self.save_users()
        return new_user

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        user = self.get_by_id(user_id)
        if not user or not verify_password(old_password, user["password_hash"], user["salt"]):
            return False
        pwd_hash, salt = hash_password(new_password)
        user["password_hash"] = pwd_hash
        user["salt"] = salt
        self.save_users()
        return True

USER_MANAGER = UserManager()

# --- FASTAPI DEPENDENCIES ---
bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> dict:
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif request and request.cookies.get("cftv_token"):
        token = request.cookies.get("cftv_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária. Envie o token Bearer no header Authorization.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = USER_MANAGER.get_by_username(payload["sub"])
    if not user or not user.get("active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inativo ou não encontrado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"]
    }

async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    return current_user

def require_role(allowed_roles: List[str]):
    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        user_role = current_user.get("role", ROLE_VIEWER)
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão negada. Requer uma das permissões: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker

require_admin = require_role([ROLE_ADMIN])
require_operator_or_admin = require_role([ROLE_ADMIN, ROLE_OPERATOR])
