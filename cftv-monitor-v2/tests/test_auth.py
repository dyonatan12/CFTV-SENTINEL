import pytest
from core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    USER_MANAGER,
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_VIEWER
)

def test_password_hashing_and_verification():
    pwd = "SenhaForte@2026_!"
    h, salt = hash_password(pwd)
    assert verify_password(pwd, h, salt) is True
    assert verify_password("SenhaErrada", h, salt) is False

def test_jwt_generation_and_decoding():
    data = {"sub": "operador_user", "role": ROLE_OPERATOR}
    token = create_access_token(data)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "operador_user"
    assert payload["role"] == ROLE_OPERATOR

def test_user_manager_crud():
    username = "test_crud_user"
    if USER_MANAGER.get_by_username(username):
        USER_MANAGER.users = [u for u in USER_MANAGER.users if u.get("username") != username]

    new_user = USER_MANAGER.create_user(username, "MinhaSenha123!", "Nome do Usuário", ROLE_OPERATOR)
    assert new_user["username"] == username
    assert new_user["role"] == ROLE_OPERATOR

    auth_success = USER_MANAGER.authenticate(username, "MinhaSenha123!")
    assert auth_success is not None

    auth_fail = USER_MANAGER.authenticate(username, "SenhaInvalida")
    assert auth_fail is None
