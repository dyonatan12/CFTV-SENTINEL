import uuid
from typing import List
from fastapi import APIRouter, HTTPException, Depends

from models.schemas import ClientModel
from core.auth import require_operator_or_admin
from state.app_state import GLOBAL_STATE

router = APIRouter(prefix="/api/clients", tags=["Clientes"])

@router.get("")
async def list_clients():
    return GLOBAL_STATE.clients

@router.post("", dependencies=[Depends(require_operator_or_admin)])
async def create_client(client: ClientModel):
    new_id = client.id or f"cli-{uuid.uuid4().hex[:6]}"
    client_dict = client.model_dump()
    client_dict["id"] = new_id
    GLOBAL_STATE.clients.append(client_dict)
    GLOBAL_STATE.save_clients()
    await GLOBAL_STATE.broadcast_sse("STATUS_UPDATE", {})
    return {"message": "Cliente cadastrado com sucesso", "client": client_dict}

@router.put("/{client_id}", dependencies=[Depends(require_operator_or_admin)])
async def update_client(client_id: str, client: ClientModel):
    for i, c in enumerate(GLOBAL_STATE.clients):
        if c.get("id") == client_id:
            updated = client.model_dump()
            updated["id"] = client_id
            GLOBAL_STATE.clients[i] = updated
            GLOBAL_STATE.save_clients()
            await GLOBAL_STATE.broadcast_sse("STATUS_UPDATE", {})
            return {"message": "Cliente atualizado com sucesso", "client": updated}
    raise HTTPException(status_code=404, detail="Cliente não encontrado")

@router.delete("/{client_id}", dependencies=[Depends(require_operator_or_admin)])
async def delete_client(client_id: str):
    initial_len = len(GLOBAL_STATE.clients)
    GLOBAL_STATE.clients = [c for c in GLOBAL_STATE.clients if c.get("id") != client_id]
    if len(GLOBAL_STATE.clients) == initial_len:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    GLOBAL_STATE.save_clients()
    await GLOBAL_STATE.broadcast_sse("STATUS_UPDATE", {})
    return {"message": "Cliente removido com sucesso"}
