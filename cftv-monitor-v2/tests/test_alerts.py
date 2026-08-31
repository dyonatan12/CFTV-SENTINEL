import pytest
from core.database import DB

def test_database_log_and_list_alerts():
    # Grava alertas de teste
    id1 = DB.log_alert(
        device_id="cam-101",
        device_name="Portão Norte",
        status="OFFLINE",
        event_type="CAMERA_DOWN",
        client_id="cli-shop",
        client_name="Shopping Mall",
        failures=3,
        channel="1",
        message="Câmera caiu"
    )
    assert id1 > 0

    id2 = DB.log_alert(
        device_id="cam-101",
        device_name="Portão Norte",
        status="ONLINE",
        event_type="CAMERA_RECOVERED",
        client_id="cli-shop",
        client_name="Shopping Mall",
        failures=0,
        channel="1",
        message="Câmera voltou"
    )
    assert id2 > 0

    # Consulta com filtro por cliente
    alerts, total = DB.list_alerts(client_id="cli-shop", limit=10)
    assert total >= 2
    assert any(a["id"] == id1 for a in alerts)
    assert any(a["id"] == id2 for a in alerts)

    # Consulta com filtro por status
    offline_alerts, _ = DB.list_alerts(status="OFFLINE")
    assert all(a["status"] == "OFFLINE" for a in offline_alerts)

def test_api_alerts_endpoints(client, auth_headers):
    # Consulta listagem via API
    resp = client.get("/api/alerts?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "alerts" in data

    # Exportação CSV
    csv_resp = client.get("/api/alerts/export/csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "Data/Hora" in csv_resp.text

    # Limpeza de alertas antigos (com admin)
    admin_headers = auth_headers("test_admin", "AdminPass123!")
    del_resp = client.delete("/api/alerts/clear?days=365", headers=admin_headers)
    assert del_resp.status_code == 200
    assert "removidos" in del_resp.json()["message"]
