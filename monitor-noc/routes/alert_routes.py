import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from core.database import DB
from core.auth import get_current_active_user, require_admin

router = APIRouter(prefix="/api/alerts", tags=["Histórico de Alertas"])

@router.get("")
async def list_alerts(
    client_id: Optional[str] = Query(None, description="Filtrar por ID do cliente"),
    device_id: Optional[str] = Query(None, description="Filtrar por ID do dispositivo"),
    status: Optional[str] = Query(None, description="Filtrar por status: ONLINE ou OFFLINE"),
    limit: int = Query(50, ge=1, le=500, description="Quantidade por página"),
    offset: int = Query(0, ge=0, description="Deslocamento para paginação")
):
    alerts, total = DB.list_alerts(
        client_id=client_id,
        device_id=device_id,
        status=status,
        limit=limit,
        offset=offset
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "alerts": alerts
    }

@router.get("/export/csv")
async def export_alerts_csv(
    client_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    alerts, _ = DB.list_alerts(client_id=client_id, status=status, limit=10000, offset=0)
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        "ID", "Data/Hora", "Cliente", "Dispositivo", "Canal", "Status", "Tipo de Evento", "Falhas", "Mensagem"
    ])
    
    for a in alerts:
        writer.writerow([
            a.get("id"),
            a.get("timestamp"),
            a.get("client_name"),
            a.get("device_name"),
            a.get("channel"),
            a.get("status"),
            a.get("event_type"),
            a.get("failures"),
            a.get("message", "").replace("\n", " ")
        ])
    
    csv_data = output.getvalue()
    output.close()

    filename = f"cftv_alertas_{client_id or 'todos'}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.delete("/clear", dependencies=[Depends(require_admin)])
async def clear_old_alerts(days: int = Query(30, ge=1, description="Dias para retenção")):
    deleted_count = DB.clear_old_alerts(days=days)
    return {"message": f"{deleted_count} alertas anteriores a {days} dias foram removidos com sucesso."}
