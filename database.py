import sqlite3
import os

_base = "/tmp" if (os.environ.get("VERCEL") or os.environ.get("RENDER")) else os.path.dirname(__file__)
DB_PATH = os.path.join(_base, "viva_cont.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate(conn, sql, *alt_sqls):
    """Run a DDL migration silently if it fails (column already exists, etc.)."""
    for s in [sql] + list(alt_sqls):
        try:
            conn.execute(s)
            conn.commit()
        except Exception:
            pass


def init_db():
    conn = get_connection()
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
            VALUES (1, '20600000000', 'VIVA CONSULTING EMPRESAS S.A.C.', 'VIVA CONSULTING',
                    'Lima, Perú', '+51 999 999 999', 'contacto@vivaconsulting.pe')
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


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    return [dict(r) for r in rows]
