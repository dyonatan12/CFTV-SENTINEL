import pytest
from core.tracker import DeviceTracker, CameraStatus, DeviceState

def test_device_state_transitions():
    cam = {"id": "cam-10", "name": "Camera 10", "ip": "192.168.1.10"}
    dev = DeviceState(cam, failure_threshold=3, recovery_threshold=2)

    assert dev.status == CameraStatus.ONLINE

    # 1ª falha -> PENDING_OFFLINE
    dev.update_result(False)
    assert dev.status == CameraStatus.PENDING_OFFLINE
    assert dev.consecutive_failures == 1

    # 2ª falha -> PENDING_OFFLINE
    dev.update_result(False)
    assert dev.status == CameraStatus.PENDING_OFFLINE

    # 3ª falha -> OFFLINE confirmado
    dev.update_result(False)
    assert dev.status == CameraStatus.OFFLINE

    # 1º sucesso -> PENDING_ONLINE
    dev.update_result(True, latency_ms=10.0)
    assert dev.status == CameraStatus.PENDING_ONLINE
    assert dev.consecutive_successes == 1

    # 2º sucesso -> ONLINE confirmado
    dev.update_result(True, latency_ms=12.0)
    assert dev.status == CameraStatus.ONLINE

def test_device_tracker_summary_and_nvr():
    cams = [
        {"id": "cam-1", "name": "NVR1-CH1", "ip": "10.0.0.1", "nvr": "NVD1", "channel": 1, "client_id": "cli-1"},
        {"id": "cam-2", "name": "NVR1-CH2", "ip": "10.0.0.1", "nvr": "NVD1", "channel": 2, "client_id": "cli-1"},
        {"id": "cam-3", "name": "NVR1-CH3", "ip": "10.0.0.1", "nvr": "NVD1", "channel": 3, "client_id": "cli-1"}
    ]
    tracker = DeviceTracker(cams, failure_threshold=2, recovery_threshold=1)
    
    summary = tracker.get_summary()
    assert summary["total"] == 3
    assert summary["online"] == 3

    # Simula queda de 2 dos 3 canais (>= 50% = NVR Down)
    tracker.get_device("cam-1").update_result(False)
    tracker.get_device("cam-1").update_result(False)
    tracker.get_device("cam-2").update_result(False)
    tracker.get_device("cam-2").update_result(False)

    tracker.evaluate_nvrs()
    nvr_group = tracker.nvrs.get("cli-1_NVD1")
    assert nvr_group is not None
    assert nvr_group.is_offline is True
