"""
conftest.py — Fixtures globales para la suite de tests VIVA CONT.

Usa SQLite en memoria (VIVA_DB_PATH=:memory: no funciona con reinicio de módulos,
por eso usamos un archivo temp que se borra al finalizar cada sesión de tests).
"""
import os
import sys
import tempfile
import pytest

# ── Forzar SQLite local antes de importar app ──────────────────────────────
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
TEST_DB = _tmp.name

os.environ["VIVA_DB_PATH"]          = TEST_DB
os.environ["TURSO_DATABASE_URL"]    = ""
os.environ["TURSO_AUTH_TOKEN"]      = ""
os.environ["SECRET_KEY"]            = "test-secret-key-viva-cont"

# Agregar raíz del proyecto al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import database  # noqa: E402 — importar DESPUÉS de setear env vars
database.DB_PATH = TEST_DB  # parchar en caliente también

import app as app_module  # noqa: E402


@pytest.fixture(scope="session")
def flask_app():
    """App configurada para testing con DB limpia."""
    flask_app = app_module.app
    flask_app.config.update({
        "TESTING":               True,
        "WTF_CSRF_ENABLED":      False,
        "SERVER_NAME":           None,
        "SESSION_COOKIE_SECURE": False,
    })
    yield flask_app
    # Cleanup DB temporal al terminar la sesión
    try:
        os.unlink(TEST_DB)
    except OSError:
        pass


@pytest.fixture(scope="session")
def client(flask_app):
    """Test client con contexto de sesión."""
    return flask_app.test_client()


@pytest.fixture
def auth_client(client):
    """Client ya autenticado como super_admin (sin 2FA)."""
    with client.session_transaction() as sess:
        sess["user_id"]       = 1
        sess["user_name"]     = "Luis Vallejos"
        sess["user_rol"]      = "super_admin"
        sess["user_email"]    = "vivacont@vivaempresasglobal.com"
        sess["username"]      = "luisvallejos"
        sess["cliente_id"]    = 1
        sess["privilegios"]   = '["estados_cuenta","analisis_bancario","estados_resultados","balance_general","facturador"]'
        sess["totp_verified"] = True
    return client


# Credenciales del super_admin sembrado por init_db()
ADMIN_USER = "luisvallejos"
ADMIN_PASS = "VivaAdmin2026!"
