"""
test_auth.py — Flujo de autenticación: login, logout, protección de rutas.
"""
import json
from tests.conftest import ADMIN_USER, ADMIN_PASS


class TestLoginPage:
    def test_get_login_returns_200(self, client):
        r = client.get("/login")
        assert r.status_code == 200

    def test_login_page_has_form(self, client):
        r = client.get("/login")
        assert b"form" in r.data.lower()

    def test_login_page_has_username_field(self, client):
        assert b"username" in client.get("/login").data.lower()


class TestLoginPost:
    def test_wrong_credentials_rejected(self, client):
        r = client.post("/login", data={
            "username": "hackerXXX",
            "password": "wrongpassword123"
        }, follow_redirects=True)
        # Debe quedarse en /login o devolver error — nunca redirigir al dashboard
        assert r.status_code == 200
        # No debe haber user_id en sesión
        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_empty_credentials_rejected(self, client):
        r = client.post("/login", data={"username": "", "password": ""})
        assert r.status_code in (200, 400)
        with client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_correct_credentials_accepted(self, client):
        """Login exitoso → sesión establecida (puede pedir 2FA o ir al dashboard)."""
        r = client.post("/login", data={
            "username": ADMIN_USER,
            "password": ADMIN_PASS
        }, follow_redirects=False)
        # 302 a dashboard o a 2FA — nunca 401/500
        assert r.status_code in (200, 302)


class TestLogout:
    def test_logout_clears_session(self, auth_client):
        auth_client.get("/logout")
        with auth_client.session_transaction() as sess:
            assert "user_id" not in sess

    def test_logout_redirects_to_login(self, auth_client):
        r = auth_client.get("/logout", follow_redirects=False)
        assert r.status_code in (302, 301)
        location = r.headers.get("Location", "")
        assert "login" in location or location == "/"


class TestProtectedRoutes:
    PROTECTED = ["/", "/facturador", "/analisis-bancario",
                 "/estados-resultados", "/balance-general",
                 "/usuarios", "/configuracion"]

    def test_unauthenticated_redirects_to_login(self, client):
        """Todas las rutas protegidas deben redirigir si no hay sesión."""
        # Limpiar sesión
        with client.session_transaction() as sess:
            sess.clear()
        for path in self.PROTECTED:
            r = client.get(path, follow_redirects=False)
            assert r.status_code in (301, 302), \
                f"Ruta {path} debería redirigir sin auth, devolvió {r.status_code}"

    def test_authenticated_can_access_dashboard(self, auth_client):
        r = auth_client.get("/", follow_redirects=True)
        assert r.status_code == 200
