from fastapi import APIRouter, HTTPException, Depends, Request, status
from models.schemas import LoginRequest, TokenResponse, ChangePasswordRequest, CreateUserRequest
from core.auth import (
    USER_MANAGER,
    create_access_token,
    get_current_active_user,
    require_admin,
    LOGIN_RATE_LIMITER
)

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if not LOGIN_RATE_LIMITER.is_allowed(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login consecutivas. Aguarde 1 minuto."
        )
    
    user = USER_MANAGER.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos."
        )
    
    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "name": user["name"],
            "role": user["role"]
        }
    }

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_active_user)):
    return current_user

@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    current_user: dict = Depends(get_current_active_user)
):
    success = USER_MANAGER.change_password(current_user["id"], req.old_password, req.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    return {"message": "Senha alterada com sucesso!"}

@router.get("/users", dependencies=[Depends(require_admin)])
async def list_users():
    return [{
        "id": u["id"],
        "username": u["username"],
        "name": u["name"],
        "role": u["role"],
        "active": u.get("active", True),
        "created_at": u.get("created_at"),
        "last_login": u.get("last_login")
    } for u in USER_MANAGER.users]

@router.post("/users", dependencies=[Depends(require_admin)])
async def create_user(req: CreateUserRequest):
    try:
        new_u = USER_MANAGER.create_user(req.username, req.password, req.name, req.role)
        return {
            "message": "Usuário criado com sucesso",
            "user": {
                "id": new_u["id"],
                "username": new_u["username"],
                "name": new_u["name"],
                "role": new_u["role"]
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
