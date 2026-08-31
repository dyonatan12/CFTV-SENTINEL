import os
import sys
import pytest
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app
from core.auth import USER_MANAGER, ROLE_ADMIN, ROLE_OPERATOR, ROLE_VIEWER, LOGIN_RATE_LIMITER
from state.app_state import GLOBAL_STATE

@pytest.fixture(scope="session")
def client():
    # Inicializa usuários de teste
    try:
        USER_MANAGER.create_user("test_admin", "AdminPass123!", "Admin Teste", ROLE_ADMIN)
    except ValueError:
        pass
    try:
        USER_MANAGER.create_user("test_operator", "OpPass123!", "Operador Teste", ROLE_OPERATOR)
    except ValueError:
        pass
    try:
        USER_MANAGER.create_user("test_viewer", "ViewPass123!", "Viewer Teste", ROLE_VIEWER)
    except ValueError:
        pass

    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def auth_headers(client):
    tokens_cache = {}
    def _get_headers(username="test_admin", password="AdminPass123!"):
        if username in tokens_cache:
            return {"Authorization": f"Bearer {tokens_cache[username]}"}
        LOGIN_RATE_LIMITER.attempts.clear()
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        if resp.status_code == 200:
            token = resp.json()["access_token"]
            tokens_cache[username] = token
            return {"Authorization": f"Bearer {token}"}
        raise RuntimeError(f"Falha de login no fixture para '{username}': {resp.status_code} {resp.text}")
    return _get_headers
