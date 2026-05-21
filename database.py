import sqlite3
import os
import json
import urllib.request

DB_PATH = os.environ.get("VIVA_DB_PATH") or os.path.join(os.path.dirname(__file__), "viva_cont.db")

_TURSO_URL   = os.environ.get("TURSO_DATABASE_URL", "")
_TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")
_USE_TURSO   = bool(_TURSO_URL and _TURSO_TOKEN)

# HTTP endpoint: libsql://host  →  https://host/v2/pipeline
_TURSO_HTTP  = (_TURSO_URL.replace("libsql://", "https://") + "/v2/pipeline") if _TURSO_URL else ""


# ── Shared row class ─────────────────────────────────────────────────────────
class _Row:
    """dict-like row: dict(row), row['col'], row[0], row.keys() all work."""
    __slots__ = ("_d", "_keys")
    def __init__(self, keys, vals):
        self._keys = list(keys)
        self._d    = dict(zip(self._keys, vals))
    def __getitem__(self, k):
        return self._d[k] if isinstance(k, str) else list(self._d.values())[k]
    def __iter__(self):        return iter(self._d.values())
    def keys(self):            return self._keys
    def items(self):           return self._d.items()
    def values(self):          return list(self._d.values())
    def get(self, k, d=None):  return self._d.get(k, d)
    def __contains__(self, k): return k in self._d


# ── Turso HTTP client (no extra packages — pure urllib) ──────────────────────
def _turso_post(stmts: list) -> list:
    """Send a list of {sql, args} to Turso and return results list."""
    body = json.dumps({"requests": [
        {"type": "execute", "stmt": s} for s in stmts
    ] + [{"type": "close"}]}).encode()
    req = urllib.request.Request(
        _TURSO_HTTP, data=body,
        headers={"Authorization": f"Bearer {_TURSO_TOKEN}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["results"]


def _to_args(params):
    out = []
    for p in (params or []):
        if p is None:
            out.append({"type": "null"})
        elif isinstance(p, int):
            out.append({"type": "integer", "value": str(p)})
        elif isinstance(p, float):
            out.append({"type": "float", "value": p if (p == p and abs(p) != float('inf')) else 0.0})
        else:
            out.append({"type": "text", "value": str(p)})
    return out


class _TursoCursor:
    def __init__(self):
        self.description = None
        self.lastrowid   = None
        self.rowcount    = 0
        self._rows       = []
        self._pos        = 0

    def _load(self, result):
        if result.get("type") != "ok":
            raise Exception(result.get("error", {}).get("message", "Turso error"))
        rs = result.get("response", {}).get("result", {})
        cols = [c["name"] for c in rs.get("cols", [])]
        if cols:
            self.description = [(c, None, None, None, None, None, None) for c in cols]
            self._rows = [
                _Row(cols, [
                    (None if v.get("type") == "null" else
                     int(v["value"]) if v.get("type") == "integer" else
                     float(v["value"]) if v.get("type") == "float" else
                     v.get("value"))
                    for v in row
                ])
                for row in rs.get("rows", [])
            ]
        self.lastrowid = rs.get("last_insert_rowid")
        self.rowcount  = rs.get("affected_row_count", 0)

    def fetchone(self):
        if self._pos >= len(self._rows): return None
        r = self._rows[self._pos]; self._pos += 1; return r

    def fetchall(self):
        r = self._rows[self._pos:]; self._pos = len(self._rows); return r

    def __iter__(self):
        return iter(self._rows[self._pos:])


class _TursoConn:
    def __init__(self):
        self._pending = []   # buffered writes (inside a transaction)
        self._in_tx   = False
        self.lastrowid = None

    def execute(self, sql, params=()):
        cur = _TursoCursor()
        sql_up = sql.strip().upper()
        if sql_up.startswith("PRAGMA"):
            return cur                   # Turso ignores PRAGMAs
        stmt = {"sql": sql, "args": _to_args(params)}
        results = _turso_post([stmt])
        cur._load(results[0])
        self.lastrowid = cur.lastrowid
        return cur

    def cursor(self):
        return _TursoCursorProxy(self)

    def commit(self):
        pass   # each execute auto-commits in Turso HTTP

    def close(self):
        pass

    def __getattr__(self, name):
        raise AttributeError(name)


class _TursoCursorProxy:
    """Proxy so app.py patterns like c=conn.cursor(); c.execute(); c.lastrowid work."""
    def __init__(self, conn):
        self._conn  = conn
        self._cur   = _TursoCursor()
        self.description = None
        self.lastrowid   = None
        self.rowcount    = 0

    def execute(self, sql, params=()):
        self._cur = self._conn.execute(sql, params)
        self.description = self._cur.description
        self.lastrowid   = self._cur.lastrowid
        self.rowcount    = self._cur.rowcount
        return self

    def fetchone(self):  return self._cur.fetchone()
    def fetchall(self):  return self._cur.fetchall()
    def __iter__(self):  return iter(self._cur)


_turso_ok  = None   # None=untested  True=working  False=failed
_turso_err = ""


def execute_batch(conn, queries: list):
    """Run multiple (sql, params) read-queries in ONE network round-trip.

    On Turso: packages all statements into a single /v2/pipeline POST.
    Turso returns N+1 results (N execute + 1 close). We filter only
    results whose response.type == "execute" to avoid cursor count mismatch.
    On SQLite: sequential (in-process, no latency).

    Returns a list of _TursoCursor objects — same count as queries.
    Raises if the count doesn't match (signals a Turso error).
    """
    if isinstance(conn, _TursoConn):
        stmts = [{"sql": sql, "args": _to_args(list(params))}
                 for sql, params in queries]
        results = _turso_post(stmts)
        out = []
        for r in results:
            if not isinstance(r, dict):
                continue
            if r.get("type") != "ok":
                # Propagate Turso execution errors
                err = r.get("error", {}).get("message", "Turso error")
                raise Exception(f"Turso batch error: {err}")
            resp = r.get("response", {})
            if resp.get("type") != "execute":
                # Skip "close" and any other non-execute responses
                continue
            cur = _TursoCursor()
            cur._load(r)
            out.append(cur)
        if len(out) != len(queries):
            raise Exception(
                f"execute_batch: expected {len(queries)} results, got {len(out)}"
            )
        return out
    else:
        # SQLite — in-process, sequential is fine
        out = []
        for sql, params in queries:
            cur = conn.cursor()
            cur.execute(sql, params)
            out.append(cur)
        return out


def _local_conn():
    def _row_fac(cursor, row):
        return _Row([d[0] for d in cursor.description], row)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = _row_fac
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def get_connection():
    global _turso_ok, _turso_err
    if _USE_TURSO:
        if _turso_ok is None:           # first call: probe the connection
            try:
                _TursoConn().execute("SELECT 1").fetchone()
                _turso_ok = True
            except Exception as e:
                _turso_ok = False
                _turso_err = str(e)
        if _turso_ok:
            return _TursoConn()
    return _local_conn()


def _migrate(conn, sql, *alt_sqls):
    """Run a DDL migration silently if it fails (column already exists, etc.)."""
    for s in [sql] + list(alt_sqls):
        try:
            conn.execute(s)
            conn.commit()
        except Exception:
            pass


def _do_init(conn):
    c = conn.cursor()

    # ── CLIENTES (tenants) ────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razon_social TEXT NOT NULL,
            nombre_comercial TEXT,
            ruc TEXT,
            email TEXT,
            telefono TEXT,
            plan TEXT DEFAULT 'basic',
            activo INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── USUARIOS ──────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT DEFAULT 'usuario',
            privilegios TEXT DEFAULT '[]',
            activo INTEGER DEFAULT 1,
            ultimo_acceso TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)

    # ── TRANSACCIONES ─────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            modulo TEXT DEFAULT 'banco',
            fecha_operacion TEXT,
            referencia TEXT,
            moneda TEXT,
            importe REAL,
            num_operacion TEXT,
            periodo TEXT,
            banco TEXT,
            fecha TEXT,
            mes TEXT,
            descripcion TEXT,
            tipo TEXT,
            detalle TEXT,
            op TEXT,
            tipo_doc TEXT,
            ruc TEXT,
            cliente_proveedor TEXT,
            num_documento TEXT,
            saldo REAL,
            doc_cont TEXT,
            comprobante TEXT,
            archivo_origen TEXT,
            periodo_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── FACTURAS ──────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            serie TEXT NOT NULL,
            correlativo TEXT NOT NULL,
            tipo_comprobante TEXT DEFAULT 'FACTURA',
            fecha_emision TEXT,
            fecha_vencimiento TEXT,
            ruc_emisor TEXT,
            razon_social_emisor TEXT,
            direccion_emisor TEXT,
            ruc_cliente TEXT,
            razon_social_cliente TEXT,
            direccion_cliente TEXT,
            moneda TEXT DEFAULT 'PEN',
            subtotal REAL DEFAULT 0,
            igv REAL DEFAULT 0,
            total REAL DEFAULT 0,
            estado TEXT DEFAULT 'BORRADOR',
            observaciones TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── FACTURA ITEMS ─────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS factura_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id INTEGER NOT NULL,
            descripcion TEXT,
            cantidad REAL DEFAULT 1,
            unidad TEXT DEFAULT 'UND',
            precio_unitario REAL DEFAULT 0,
            descuento REAL DEFAULT 0,
            valor_venta REAL DEFAULT 0,
            igv_item REAL DEFAULT 0,
            precio_total REAL DEFAULT 0,
            FOREIGN KEY (factura_id) REFERENCES facturas(id) ON DELETE CASCADE
        )
    """)

    # ── CUENTAS BANCARIAS ─────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS cuentas_bancarias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            banco TEXT NOT NULL,
            numero_cuenta TEXT,
            moneda TEXT DEFAULT 'PEN',
            saldo_actual REAL DEFAULT 0,
            activa INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── PERÍODOS CARGADOS ─────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS periodos_cargados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            label TEXT,
            mes TEXT,
            anio INTEGER,
            banco TEXT,
            archivo TEXT,
            total_transacciones INTEGER DEFAULT 0,
            total_ingresos REAL DEFAULT 0,
            total_egresos REAL DEFAULT 0,
            saldo_inicial REAL DEFAULT 0,
            saldo_final REAL DEFAULT 0,
            analysis_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── IMPORTACIONES ─────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS importaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            nombre_archivo TEXT,
            tipo_fuente TEXT,
            url_fuente TEXT,
            registros_importados INTEGER DEFAULT 0,
            estado TEXT DEFAULT 'PENDIENTE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── EMPRESA (configuración por cliente) ───────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS empresa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER UNIQUE,
            ruc TEXT,
            razon_social TEXT,
            nombre_comercial TEXT,
            direccion TEXT,
            telefono TEXT,
            email TEXT,
            regimen TEXT DEFAULT 'GENERAL',
            logo_path TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── ESTADO DE RESULTADOS ──────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS estados_resultados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            periodo_label TEXT,
            mes TEXT,
            anio INTEGER,
            moneda TEXT DEFAULT 'PEN',
            ventas_netas REAL DEFAULT 0,
            otros_ingresos REAL DEFAULT 0,
            total_ingresos REAL DEFAULT 0,
            costo_ventas REAL DEFAULT 0,
            utilidad_bruta REAL DEFAULT 0,
            gastos_administrativos REAL DEFAULT 0,
            gastos_ventas REAL DEFAULT 0,
            total_gastos_operativos REAL DEFAULT 0,
            ebitda REAL DEFAULT 0,
            depreciacion_amortizacion REAL DEFAULT 0,
            ebit REAL DEFAULT 0,
            gastos_financieros REAL DEFAULT 0,
            otros_gastos_netos REAL DEFAULT 0,
            utilidad_antes_impuestos REAL DEFAULT 0,
            impuesto_renta REAL DEFAULT 0,
            utilidad_neta REAL DEFAULT 0,
            archivo_origen TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── BALANCE GENERAL ───────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS balance_general (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            periodo_label TEXT,
            mes TEXT,
            anio INTEGER,
            moneda TEXT DEFAULT 'PEN',
            caja_bancos REAL DEFAULT 0,
            cuentas_cobrar REAL DEFAULT 0,
            inventarios REAL DEFAULT 0,
            otros_ac REAL DEFAULT 0,
            total_activo_corriente REAL DEFAULT 0,
            inmueble_maquinaria REAL DEFAULT 0,
            depreciacion_acumulada REAL DEFAULT 0,
            activos_intangibles REAL DEFAULT 0,
            otros_anc REAL DEFAULT 0,
            total_activo_no_corriente REAL DEFAULT 0,
            total_activo REAL DEFAULT 0,
            cuentas_pagar REAL DEFAULT 0,
            prestamos_cp REAL DEFAULT 0,
            otros_pc REAL DEFAULT 0,
            total_pasivo_corriente REAL DEFAULT 0,
            deuda_lp REAL DEFAULT 0,
            otros_pnc REAL DEFAULT 0,
            total_pasivo_no_corriente REAL DEFAULT 0,
            total_pasivo REAL DEFAULT 0,
            capital_social REAL DEFAULT 0,
            reservas REAL DEFAULT 0,
            utilidades_retenidas REAL DEFAULT 0,
            resultado_ejercicio REAL DEFAULT 0,
            total_patrimonio REAL DEFAULT 0,
            total_pasivo_patrimonio REAL DEFAULT 0,
            archivo_origen TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── AUDIT LOG ─────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            usuario_id INTEGER,
            username TEXT,
            accion TEXT NOT NULL,
            modulo TEXT,
            detalle TEXT,
            ip TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── ALERTAS ───────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            mensaje TEXT,
            nivel TEXT DEFAULT 'info',
            leida INTEGER DEFAULT 0,
            url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── USUARIOS ROLES ────────────────────────────────────────
    _migrate(conn, "ALTER TABLE usuarios ADD COLUMN rol TEXT DEFAULT 'usuario'")
    _migrate(conn, "ALTER TABLE usuarios ADD COLUMN activo INTEGER DEFAULT 1")
    _migrate(conn, "ALTER TABLE usuarios ADD COLUMN ultimo_acceso TIMESTAMP")

    # ── ÍNDICES DE RENDIMIENTO ────────────────────────────
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_transacciones_cliente ON transacciones(cliente_id)",
        "CREATE INDEX IF NOT EXISTS idx_transacciones_modulo  ON transacciones(cliente_id, modulo)",
        "CREATE INDEX IF NOT EXISTS idx_transacciones_periodo ON transacciones(periodo_id)",
        "CREATE INDEX IF NOT EXISTS idx_facturas_cliente      ON facturas(cliente_id)",
        "CREATE INDEX IF NOT EXISTS idx_periodos_cliente      ON periodos_cargados(cliente_id)",
        "CREATE INDEX IF NOT EXISTS idx_er_cliente            ON estados_resultados(cliente_id)",
        "CREATE INDEX IF NOT EXISTS idx_bg_cliente            ON balance_general(cliente_id)",
        "CREATE INDEX IF NOT EXISTS idx_importaciones_cliente ON importaciones(cliente_id)",
        "CREATE INDEX IF NOT EXISTS idx_transacciones_importacion ON transacciones(importacion_id)",
        "CREATE INDEX IF NOT EXISTS idx_usuarios_cliente      ON usuarios(cliente_id)",
        "CREATE INDEX IF NOT EXISTS idx_usuarios_username     ON usuarios(username)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_cliente     ON audit_log(cliente_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_log_created     ON audit_log(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_alertas_cliente       ON alertas(cliente_id, leida)",
    ]:
        try:
            conn.execute(idx_sql)
        except Exception:
            pass

    conn.commit()

    # ── MIGRACIONES (tablas preexistentes) ────────────────
    for tbl in ["usuarios", "transacciones", "facturas", "periodos_cargados",
                "importaciones", "estados_resultados", "balance_general",
                "cuentas_bancarias"]:
        _migrate(conn, f"ALTER TABLE {tbl} ADD COLUMN cliente_id INTEGER")

    _migrate(conn, "ALTER TABLE transacciones ADD COLUMN modulo TEXT DEFAULT 'banco'")
    _migrate(conn, "ALTER TABLE transacciones ADD COLUMN periodo_id INTEGER")
    _migrate(conn, "ALTER TABLE transacciones ADD COLUMN importacion_id INTEGER")
    _migrate(conn, "ALTER TABLE usuarios ADD COLUMN privilegios TEXT DEFAULT '[]'")
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN cliente_id INTEGER UNIQUE")

    # ── NUBEFACT / SUNAT columns ──────────────────────────
    _migrate(conn, "ALTER TABLE facturas ADD COLUMN sunat_estado TEXT")
    _migrate(conn, "ALTER TABLE facturas ADD COLUMN sunat_descripcion TEXT")
    _migrate(conn, "ALTER TABLE facturas ADD COLUMN enlace_pdf TEXT")
    _migrate(conn, "ALTER TABLE facturas ADD COLUMN enlace_xml TEXT")
    _migrate(conn, "ALTER TABLE facturas ADD COLUMN codigo_qr TEXT")
    _migrate(conn, "ALTER TABLE facturas ADD COLUMN nubefact_id TEXT")
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN nubefact_token TEXT")
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN nubefact_modo TEXT DEFAULT 'demo'")
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN nubefact_ruta TEXT")
    # Personalización de comprobantes
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN logo_base64 TEXT")
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN factura_color TEXT DEFAULT '#1a3c6e'")
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN factura_footer TEXT")
    # Series de comprobantes configurables
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN serie_factura TEXT DEFAULT 'F001'")
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN serie_boleta TEXT DEFAULT 'B001'")
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN serie_nc TEXT DEFAULT 'FC01'")
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN serie_nd TEXT DEFAULT 'FD01'")
    _migrate(conn, "ALTER TABLE empresa ADD COLUMN serie_lc TEXT DEFAULT 'LC01'")

    # ── 2FA columns ───────────────────────────────────────
    _migrate(conn, "ALTER TABLE usuarios ADD COLUMN totp_secret TEXT")
    _migrate(conn, "ALTER TABLE usuarios ADD COLUMN totp_habilitado INTEGER DEFAULT 0")
    _migrate(conn, "ALTER TABLE clientes ADD COLUMN plan TEXT DEFAULT 'basic'")
    _migrate(conn, "ALTER TABLE clientes ADD COLUMN activo INTEGER DEFAULT 1")

    # ── CLIENTE RAÍZ: Viva Consulting (id=1) ──────────────
    c.execute("SELECT COUNT(*) FROM clientes WHERE id=1")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO clientes (id, razon_social, nombre_comercial, ruc, email, plan)
            VALUES (1, 'VIVA CONSULTING EMPRESAS S.A.C.', 'VIVA CONSULTING',
                    '20600000000', 'contacto@vivaconsulting.pe', 'enterprise')
        """)
        conn.commit()

    # ── EMPRESA de Viva Consulting ────────────────────────
    c.execute("SELECT COUNT(*) FROM empresa WHERE cliente_id=1")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO empresa (cliente_id, ruc, razon_social, nombre_comercial, direccion, telefono, email)
            VALUES (1, '20607308056', 'VIVA CONSULTING EMPRESAS S.A.C.', 'VIVA CONSULTING',
                    'Lima, Perú', '+51 999 999 999', 'contacto@vivaconsulting.pe')
        """)
    else:
        # Fix RUC if it was placeholder or blank
        c.execute("""
            UPDATE empresa SET ruc='20607308056', razon_social='VIVA CONSULTING EMPRESAS S.A.C.'
            WHERE cliente_id=1 AND (ruc IS NULL OR ruc='' OR ruc='20600000000')
        """)
        conn.commit()

    # ── Asignar datos huérfanos a cliente_id=1 ────────────
    for tbl in ["transacciones", "facturas", "periodos_cargados",
                "importaciones", "estados_resultados", "balance_general",
                "cuentas_bancarias"]:
        conn.execute(f"UPDATE {tbl} SET cliente_id=1 WHERE cliente_id IS NULL")
    conn.execute("UPDATE empresa SET cliente_id=1 WHERE cliente_id IS NULL")
    conn.commit()

    # ── SUPER ADMIN: Luis Vallejos ────────────────────────
    from werkzeug.security import generate_password_hash
    _fast_hash = generate_password_hash('VivaAdmin2026!', method='pbkdf2:sha256:50000')
    _all_privs = '["estados_cuenta","analisis_bancario","estados_resultados","balance_general","facturador"]'

    c.execute("SELECT COUNT(*) FROM usuarios WHERE rol='super_admin'")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO usuarios (cliente_id, nombre, email, username, password_hash, rol, privilegios)
            VALUES (1, ?, ?, ?, ?, 'super_admin', ?)
        """, ('Luis Vallejos Rodriguez', 'vivacont@vivaempresasglobal.com',
              'luisvallejos', _fast_hash, _all_privs))
    else:
        # Asegurar cliente_id=1 y privilegios completos en super_admin
        conn.execute(
            "UPDATE usuarios SET cliente_id=1, privilegios=? WHERE rol='super_admin' AND cliente_id IS NULL",
            (_all_privs,)
        )
        # Migrar hash lento al hash rápido
        row = c.execute("SELECT password_hash FROM usuarios WHERE username='luisvallejos'").fetchone()
        if row:
            parts = row[0].split(':')
            if len(parts) >= 3:
                iters = parts[2].split('$')[0]
                if iters.isdigit() and int(iters) > 100000:
                    c.execute("UPDATE usuarios SET password_hash=? WHERE username='luisvallejos'",
                              (_fast_hash,))

    conn.commit()
    conn.close()


def init_db():
    global _turso_ok, _turso_err
    try:
        _do_init(get_connection())
    except Exception as e:
        # Turso failed during init — disable it and retry with local SQLite
        _turso_ok = False
        _turso_err = f"init_db Turso error: {e}"
        try:
            _do_init(_local_conn())
        except Exception as e2:
            # Log but don't crash — app must start
            import sys
            print(f"[database] init_db local fallback also failed: {e2}", file=sys.stderr)


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    return [dict(r) for r in rows]
