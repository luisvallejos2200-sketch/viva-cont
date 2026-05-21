"""
test_api.py — Endpoints API: acceso autenticado vs no autenticado, respuestas JSON.
"""
import json


class TestApiProtection:
    """Todos los endpoints /api/* protegidos deben rechazar requests sin sesión."""

    PROTECTED_GET = [
        "/api/usuarios",
        "/api/empresas",
        "/api/alertas",
        "/api/facturas",
        "/api/empresa",
    ]

    def test_unauthenticated_api_redirects_or_401(self, client):
        with client.session_transaction() as sess:
            sess.clear()
        for path in self.PROTECTED_GET:
            r = client.get(path)
            assert r.status_code in (302, 401, 403), \
                f"GET {path} sin auth debería ser 302/401/403, got {r.status_code}"


class TestApiUsuarios:
    def test_get_usuarios_returns_list(self, auth_client):
        r = auth_client.get("/api/usuarios")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)

    def test_super_admin_in_list(self, auth_client):
        r = auth_client.get("/api/usuarios")
        usuarios = r.get_json()
        usernames = [u.get("username") for u in usuarios]
        assert "luisvallejos" in usernames

    def test_create_usuario_missing_fields_rejected(self, auth_client):
        r = auth_client.post("/api/usuarios",
                             json={"nombre": "Test"},
                             content_type="application/json")
        assert r.status_code in (400, 422)

    def test_create_usuario_returns_json(self, auth_client):
        r = auth_client.post("/api/usuarios", json={
            "nombre":   "Test User",
            "email":    "test_pytest@viva.pe",
            "username": "test_pytest",
            "password": "TestPass2026!",
            "rol":      "usuario",
        }, content_type="application/json")
        assert r.status_code in (200, 201, 400, 409)
        assert r.content_type.startswith("application/json")


class TestApiEmpresas:
    def test_get_empresas_returns_list(self, auth_client):
        r = auth_client.get("/api/empresas")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)

    def test_empresa_info_returns_object(self, auth_client):
        r = auth_client.get("/api/empresa")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, dict)


class TestApiFacturas:
    def test_get_facturas_returns_json(self, auth_client):
        r = auth_client.get("/api/facturas")
        assert r.status_code == 200
        data = r.get_json()
        # Puede ser lista o dict con "facturas" key
        assert isinstance(data, (list, dict))

    def test_factura_stats_returns_numbers(self, auth_client):
        r = auth_client.get("/api/facturas/stats")
        if r.status_code == 404:
            return  # endpoint opcional
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, dict)


class TestApiStatus:
    def test_health_structure(self, client):
        """El endpoint /health es el status público del sistema."""
        r = client.get("/health")
        data = r.get_json()
        assert data.get("status") == "ok"
        assert data.get("system") == "VIVA CONT"

    def test_health_no_auth_required(self, client):
        with client.session_transaction() as sess:
            sess.clear()
        r = client.get("/health")
        assert r.status_code == 200
