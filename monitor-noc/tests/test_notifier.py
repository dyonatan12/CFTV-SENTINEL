import pytest
from core.notifier import NotificationService, format_template, convert_to_html

def test_format_template():
    tpl = "Alerta: Câmera {camera_name} do cliente {client_name} caiu com {failures} falhas."
    ctx = {"camera_name": "Portão 1", "client_name": "Empresa ABC", "failures": 3}
    res = format_template(tpl, ctx)
    assert res == "Alerta: Câmera Portão 1 do cliente Empresa ABC caiu com 3 falhas."

def test_convert_to_html():
    markdown_text = "*Alerta Crítico*: `cam-01` offline"
    html_text = convert_to_html(markdown_text)
    assert "<b>Alerta Crítico</b>" in html_text
    assert "<code>cam-01</code>" in html_text

def test_flood_suppression():
    notifier = NotificationService()
    notifier.cooldown_seconds = 100
    
    # 1ª chamada não deve suprimir
    assert notifier.should_suppress_flood("cam_1") is False
    # 2ª chamada imediata DEVE suprimir
    assert notifier.should_suppress_flood("cam_1") is True
    # Outro dispositivo não é afetado
    assert notifier.should_suppress_flood("cam_2") is False
