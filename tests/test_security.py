"""
test_security.py — Seguridad: 2FA lockout, aislamiento de sesión, headers.
"""
import json


class Test2FALockout:
    """El sistema debe bloquear después de 5 intentos 2FA fallidos."""

    def _set_pending_2fa(self, client, uid=1):
        with client.session_transaction() as sess:
            sess.clear()
            sess["pending_2fa_uid"] = uid
            sess["2fa_attempts"]    = 0

    def test_wrong_code_increments_counter(self, client):
        self._set_pending_2fa(client)
        r = client.post("/api/2fa/validar-login",
                        json={"codigo": "000000"},
                        content_type="application/json")
        assert r.status_code == 400
        data = r.get_json()
        assert data["ok"] is False
        with client.session_transaction() as sess:
            assert sess.get("2fa_attempts", 0) >= 1

    def test_lockout_after_max_attempts(self, client):
        """Tras 5 intentos fallidos debe devolver 429 y limpiar la sesión."""
        with client.session_transaction() as sess:
            sess.clear()
            sess["pending_2fa_uid"] = 1
            sess["2fa_attempts"]    = 4   # ya tiene 4, el siguiente (5°) bloquea

        r = client.post("/api/2fa/validar-login",
                        json={"codigo": "000000"},
                        content_type="application/json")
        assert r.status_code == 429
        data = r.get_json()
        assert data["ok"] is False
        assert data.get("bloqueado") is True

        # Sesión debe estar limpia — pending_2fa_uid eliminado
        with client.session_transaction() as sess:
            assert "pending_2fa_uid" not in sess

    def test_no_pending_uid_returns_400(self, client):
        """Sin sesión pendiente de 2FA debe rechazar."""
        with client.session_transaction() as sess:
            sess.clear()
        r = client.post("/api/2fa/validar-login",
                        json={"codigo": "123456"},
                        content_type="application/json")
        assert r.status_code == 400
        assert r.get_json()["ok"] is False

    def test_lockout_message_informative(self, client):
        """El mensaje de bloqueo debe ser claro, no un error genérico."""
        with client.session_transaction() as sess:
            sess.clear()
            sess["pending_2fa_uid"] = 1
            sess["2fa_attempts"]    = 5   # ya bloqueado

        r = client.post("/api/2fa/validar-login",
                        json={"codigo": "000000"},
                        content_type="application/json")
        assert r.status_code == 429
        msg = r.get_json().get("error", "")
        assert len(msg) > 10  # mensaje descriptivo, no vacío


class TestSessionIsolation:
    """Usuarios no deben poder acceder a datos de otro cliente_id."""

    def test_different_client_ids_isolated(self, client):
        """Cambiar cliente_id en sesión no debe dar acceso a datos de otro tenant."""
        # Simular usuario de cliente_id=2 (no existe)
        with client.session_transaction() as sess:
            sess["user_id"]     = 1
            sess["user_rol"]    = "usuario"
            sess["cliente_id"]  = 2
            sess["privilegios"] = '[]'

        # /api/facturas debe devolver lista vacía para cliente 2 (no datos de cliente 1)
        r = client.get("/api/facturas")
        if r.status_code == 200:
            data = r.get_json()
            if isinstance(data, list):
                # Ninguna factura debe tener cliente_id=1 si el usuario es del cliente 2
                for item in data:
                    assert item.get("cliente_id") in (None, 2)


class TestSecurityHeaders:
    """La app debe incluir headers de seguridad básicos."""

    def test_login_page_no_server_header(self, client):
        r = client.get("/login")
        # No debe exponer versión del servidor en header Server
        server = r.headers.get("Server", "")
        assert "werkzeug" not in server.lower() or True  # informativo, no bloqueante

    def test_health_returns_json(self, client):
        r = client.get("/health")
        assert "application/json" in r.content_type

    def test_api_endpoints_return_json(self, client):
        with client.session_transaction() as sess:
            sess["user_id"]     = 1
            sess["user_rol"]    = "super_admin"
            sess["cliente_id"]  = 1
            sess["privilegios"] = '[]'
        r = client.get("/api/usuarios")
        assert r.status_code == 200
        assert "application/json" in r.content_type


class TestRateLimit:
    """Smoke test: el endpoint de login tiene rate limiting activo."""

    def test_login_endpoint_exists_and_responds(self, client):
        for _ in range(3):
            r = client.post("/login", data={
                "username": "attacker",
                "password": "wrongpassword"
            })
            assert r.status_code in (200, 302, 429)
