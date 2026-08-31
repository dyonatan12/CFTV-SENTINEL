import pytest

def test_api_status_public(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "devices" in data

def test_api_health_and_ready(client):
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"] == "healthy"
    assert health_data["service"] == "cftv-monitor-v2"
    assert "devices" in health_data

    ready_resp = client.get("/api/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "ready"

def test_api_metrics_prometheus(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "cftv_cameras_total" in text
    assert "cftv_cameras_online" in text
    assert "cftv_scan_cycle_total" in text

def test_api_auth_login_flow(client):
    resp_fail = client.post("/api/auth/login", json={"username": "test_admin", "password": "wrong"})
    assert resp_fail.status_code == 401

    resp_ok = client.post("/api/auth/login", json={"username": "test_admin", "password": "AdminPass123!"})
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert "access_token" in data
    assert data["user"]["username"] == "test_admin"

def test_api_camera_crud_and_rbac(client, auth_headers):
    resp_unauth = client.post("/api/cameras", json={"name": "Cam Sem Auth", "ip": "192.168.1.10"})
    assert resp_unauth.status_code == 401

    op_headers = auth_headers("test_operator", "OpPass123!")
    resp_create = client.post("/api/cameras", json={
        "name": "Câmera Hall Principal",
        "ip": "192.168.1.200",
        "password": "senha_da_camera"
    }, headers=op_headers)
    assert resp_create.status_code == 200
    cam = resp_create.json()["camera"]
    assert cam["name"] == "Câmera Hall Principal"
    assert cam["password"] == "********"
    assert cam["has_password"] is True
    cam_id = cam["id"]

    view_headers = auth_headers("test_viewer", "ViewPass123!")
    resp_del_viewer = client.delete(f"/api/cameras/{cam_id}", headers=view_headers)
    assert resp_del_viewer.status_code == 403

    resp_del_op = client.delete(f"/api/cameras/{cam_id}", headers=op_headers)
    assert resp_del_op.status_code == 200

def test_api_clients_crud(client, auth_headers):
    admin_headers = auth_headers("test_admin", "AdminPass123!")
    resp = client.post("/api/clients", json={
        "name": "Cliente Shopping Center",
        "contact_name": "Gerente Carlos",
        "whatsapp": "5511999998888"
    }, headers=admin_headers)
    assert resp.status_code == 200
    cli = resp.json()["client"]
    assert cli["name"] == "Cliente Shopping Center"
    cli_id = cli["id"]

    list_resp = client.get("/api/clients")
    assert list_resp.status_code == 200
    assert any(c["id"] == cli_id for c in list_resp.json())

    del_resp = client.delete(f"/api/clients/{cli_id}", headers=admin_headers)
    assert del_resp.status_code == 200
