import sqlite3
import os

# En Vercel/serverless el filesystem raíz es read-only; usar /tmp
_base = "/tmp" if os.environ.get("VERCEL") else os.path.dirname(__file__)
DB_PATH = os.path.join(_base, "viva_cont.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Tabla principal de transacciones
    c.execute("""
        CREATE TABLE IF NOT EXISTS transacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migración: agregar columna modulo si no existe
    try:
        c.execute("ALTER TABLE transacciones ADD COLUMN modulo TEXT DEFAULT 'banco'")
        conn.commit()
    except Exception:
        pass

    # Tabla de facturas electrónicas
    c.execute("""
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # Tabla de items de facturas
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

    # Tabla de cuentas bancarias
    c.execute("""
        CREATE TABLE IF NOT EXISTS cuentas_bancarias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            banco TEXT NOT NULL,
            numero_cuenta TEXT,
            moneda TEXT DEFAULT 'PEN',
            saldo_actual REAL DEFAULT 0,
            activa INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabla de períodos cargados (un período = un estado de cuenta subido)
    c.execute("""
        CREATE TABLE IF NOT EXISTS periodos_cargados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    # Migración: agregar periodo_id a transacciones si no existe
    try:
        c.execute("ALTER TABLE transacciones ADD COLUMN periodo_id INTEGER")
        conn.commit()
    except Exception:
        pass

    # Tabla de importaciones de datos
    c.execute("""
        CREATE TABLE IF NOT EXISTS importaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_archivo TEXT,
            tipo_fuente TEXT,
            url_fuente TEXT,
            registros_importados INTEGER DEFAULT 0,
            estado TEXT DEFAULT 'PENDIENTE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabla de configuración de la empresa
    c.execute("""
        CREATE TABLE IF NOT EXISTS empresa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # Seed empresa por defecto si no existe
    c.execute("SELECT COUNT(*) FROM empresa")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO empresa (ruc, razon_social, nombre_comercial, direccion, telefono, email)
            VALUES ('20600000000', 'VIVA CONSULTING EMPRESAS S.A.C.', 'VIVA CONSULTING',
                    'Lima, Perú', '+51 999 999 999', 'contacto@vivaconsulting.pe')
        """)

    # Tabla Estado de Resultados
    c.execute("""
        CREATE TABLE IF NOT EXISTS estados_resultados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # Tabla Balance General
    c.execute("""
        CREATE TABLE IF NOT EXISTS balance_general (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # Tabla de usuarios del sistema
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT DEFAULT 'admin',
            activo INTEGER DEFAULT 1,
            ultimo_acceso TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Super Admin por defecto: Luis Vallejos
    from werkzeug.security import generate_password_hash
    c.execute("SELECT COUNT(*) FROM usuarios WHERE rol='super_admin'")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO usuarios (nombre, email, username, password_hash, rol)
            VALUES (?, ?, ?, ?, 'super_admin')
        """, (
            'Luis Vallejos Rodriguez',
            'vivacont@vivaempresasglobal.com',
            'luisvallejos',
            generate_password_hash('VivaAdmin2026!', method='pbkdf2:sha256')
        ))

    conn.commit()
    conn.close()


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows):
    return [dict(r) for r in rows]
