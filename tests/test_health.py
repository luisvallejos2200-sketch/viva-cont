"""
test_health.py — Endpoints públicos: /health y /api/status.
Estos deben responder 200 sin autenticación.
"""


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data is not None
    assert data.get("status") == "ok"


def test_health_has_turso_field(client):
    """El endpoint /health debe reportar estado de la DB (campo 'turso')."""
    r = client.get("/health")
    data = r.get_json()
    assert "turso" in data or "env" in data


def test_health_has_version(client):
    r = client.get("/health")
    data = r.get_json()
    assert "version" in data


def test_health_has_uptime(client):
    r = client.get("/health")
    data = r.get_json()
    assert "uptime" in data or "uptime_s" in data
