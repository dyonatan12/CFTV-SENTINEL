import pytest
from core.checker import check_camera_tcp, mock_check_camera, check_camera_health

@pytest.mark.asyncio
async def test_mock_check_camera():
    ok, latency = await mock_check_camera("cam-001")
    assert ok is True
    assert latency > 0

    fail_ok, _ = await mock_check_camera("cam-004")
    assert fail_ok is False

@pytest.mark.asyncio
async def test_check_camera_health_mock():
    cam_data = {"id": "cam-001", "name": "Cam Test", "ip": "127.0.0.1"}
    ok, latency = await check_camera_health(cam_data, is_mock=True)
    assert ok is True
    assert latency > 0

@pytest.mark.asyncio
async def test_check_camera_tcp_unreachable():
    # IP inexistente / inacessível em loopback na porta 59999
    ok, latency = await check_camera_tcp("192.0.2.1", 59999, timeout=0.2)
    assert ok is False
    assert latency == 0.0
