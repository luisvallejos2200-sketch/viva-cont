"""
VIVA CONT – Procesador de PDFs Bancarios
Estrategias múltiples para extraer transacciones de PDFs de BCP, BBVA, Interbank y Scotiabank.
"""
import re
import io
from datetime import datetime
from collections import defaultdict

# ── Constantes ────────────────────────────────────────────────
MESES_ES = {
    1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
    7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre",
}
MESES_MAP = {
    "ene":"Enero","feb":"Febrero","mar":"Marzo","abr":"Abril","may":"Mayo","jun":"Junio",
    "jul":"Julio","ago":"Agosto","sep":"Septiembre","oct":"Octubre","nov":"Noviembre","dic":"Diciembre",
    "jan":"Enero","aug":"Agosto","dec":"Diciembre",
}

DATE_PATTERNS = [
    re.compile(r"\b(\d{2})[/\-](\d{2})[/\-](\d{4})\b"),              # DD/MM/YYYY  DD-MM-YYYY
    re.compile(r"\b(\d{4})[/\-](\d{2})[/\-](\d{2})\b"),              # YYYY-MM-DD
    re.compile(r"\b(\d{2})[/\-](\d{2})[/\-](\d{2})\b"),              # DD/MM/YY
    re.compile(r"\b(\d{1,2})[/\-]([A-Za-z]{3})[\-\s]+(\d{4})\b"),   # DD-ENE-2026 / DD/ENE/2026
    re.compile(r"\b(\d{1,2})[/\-]([A-Za-z]{3})\b"),                  # DD-ENE (sin año, usa año actual)
]

# Meses en español para parsear fechas tipo DD-ENE-2026
MESES_ABREV = {
    "ene":1,"feb":2,"mar":3,"abr":4,"may":5,"jun":6,
    "jul":7,"ago":8,"sep":9,"oct":10,"nov":11,"dic":12,
    "jan":1,"aug":8,"dec":12,"apr":4,"jun":6,"oct":10,
}

# Montos: acepta 1,234.56 | 1.234,56 | 1234.56 | 1234,56 | 50.00
# Orden: primero formatos con separador de miles, luego simple
AMOUNT_RE = re.compile(
    r"(?<!\w)(-?)"
    r"("
    r"\d{1,3}(?:[,\.]\d{3})+[,\.]\d{2}"   # 1,234.56 ó 1.234,56
    r"|"
    r"\d+[,\.]\d{2}"                        # 1234.56 ó 1234,56 ó 50.00
    r")"
    r"(?!\d)"
)

TIPO_MAP = {
    "TRAN": "TRANSFERENCIA", "TRANSF": "TRANSFERENCIA", "TRANSFER": "TRANSFERENCIA",
    "ITF": "COBRO", "MANT": "COBRO", "MANTENIM": "COBRO", "COM.": "COBRO",
    "COMISION": "COBRO", "ENVIO": "COBRO", "INTERES": "COBRO", "PORTE": "COBRO",
    "CARGO": "COBRO", "COBRO": "COBRO",
    "PAGO": "PAGO", "MOV": "PAGO", "MOVI": "PAGO", "TDPC": "PAGO",
    "ABONO": "ABONO", "DEPOSITO": "ABONO", "YAPE": "YAPE", "PLIN": "YAPE",
}


# ══════════════════════════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════════════════════════

def _detect_tipo(texto: str) -> str:
    up = (texto or "").upper()
    for key, val in TIPO_MAP.items():
        if key in up:
            return val
    return "OTRO"


def _parse_amount(raw: str) -> float:
    """Convierte cadena de monto a float, acepta coma o punto como decimal."""
    if not raw:
        return 0.0
    s = raw.strip().lstrip("+-").replace(" ", "")
    # Detecta formato europeo (1.234,56) vs anglosajón (1,234.56)
    if re.search(r"\d,\d{2}$", s):          # termina en ,XX → europeo
        s = s.replace(".", "").replace(",", ".")
    elif re.search(r"\d\.\d{2}$", s):       # termina en .XX → anglosajón
        s = s.replace(",", "")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_date(raw: str):
    """Devuelve (datetime, str_iso) o None. Soporta DD/MM/YYYY, DD-ENE-2026, YYYY-MM-DD."""
    if not raw:
        return None
    raw = raw.strip()

    # Patrón 0: DD/MM/YYYY o DD-MM-YYYY (numérico)
    m = DATE_PATTERNS[0].search(raw)
    if m:
        iso = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        try:
            dt = datetime.strptime(iso, "%Y-%m-%d")
            return dt, iso
        except ValueError:
            pass

    # Patrón 1: YYYY-MM-DD
    m = DATE_PATTERNS[1].search(raw)
    if m:
        iso = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        try:
            dt = datetime.strptime(iso, "%Y-%m-%d")
            return dt, iso
        except ValueError:
            pass

    # Patrón 2: DD/MM/YY
    m = DATE_PATTERNS[2].search(raw)
    if m:
        iso = f"20{m.group(3)}-{m.group(2)}-{m.group(1)}"
        try:
            dt = datetime.strptime(iso, "%Y-%m-%d")
            return dt, iso
        except ValueError:
            pass

    # Patrón 3: DD-ENE-2026 o DD/ENE/2026 (BCP estilo)
    m = DATE_PATTERNS[3].search(raw)
    if m:
        day  = int(m.group(1))
        mes  = MESES_ABREV.get(m.group(2).lower())
        year = int(m.group(3))
        if mes and 1 <= day <= 31 and 2000 <= year <= 2099:
            try:
                dt  = datetime(year, mes, day)
                iso = dt.strftime("%Y-%m-%d")
                return dt, iso
            except ValueError:
                pass

    # Patrón 4: DD-ENE sin año → usar año actual
    m = DATE_PATTERNS[4].search(raw)
    if m:
        day  = int(m.group(1))
        mes  = MESES_ABREV.get(m.group(2).lower())
        year = datetime.now().year
        if mes and 1 <= day <= 31:
            try:
                dt  = datetime(year, mes, day)
                iso = dt.strftime("%Y-%m-%d")
                return dt, iso
            except ValueError:
                pass

    return None


def _month_name(dt: datetime) -> str:
    return MESES_ES.get(dt.month, "")


def _make_tx(fecha_dt, fecha_str, desc, importe, saldo, banco, archivo=""):
    return {
        "fecha_operacion": fecha_str,
        "referencia":      desc[:80] if desc else "",
        "moneda":          "PEN",
        "importe":         round(importe, 2),
        "num_operacion":   "",
        "periodo":         fecha_str[:7] if len(fecha_str) >= 7 else "",
        "banco":           banco,
        "fecha":           fecha_str,
        "mes":             _month_name(fecha_dt),
        "descripcion":     desc[:120] if desc else "",
        "tipo":            _detect_tipo(desc),
        "detalle":         desc[:120] if desc else "",
        "op":              "",
        "tipo_doc":        "",
        "ruc":             "",
        "cliente_proveedor": "",
        "num_documento":   "",
        "saldo":           round(saldo, 2),
        "doc_cont":        "",
        "comprobante":     "",
        "archivo_origen":  archivo,
    }


# ══════════════════════════════════════════════════════════════
# ESTRATEGIA 1: pdfplumber – tablas estructuradas
# ══════════════════════════════════════════════════════════════

def _strategy_tables(pdf, banco, archivo):
    """Intenta extraer tablas con pdfplumber — procesa TODAS las páginas."""
    txs = []
    table_settings = [
        {},
        {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
        {"vertical_strategy": "text",  "horizontal_strategy": "text"},
        {"vertical_strategy": "lines_strict", "horizontal_strategy": "lines_strict"},
    ]
    seen = set()  # evitar filas duplicadas entre configuraciones

    for page in pdf.pages:
        page_txs = []
        for settings in table_settings:
            try:
                tables = page.extract_tables(table_settings=settings) if settings else page.extract_tables()
            except Exception:
                continue
            for table in (tables or []):
                for row in table:
                    if not row:
                        continue
                    cells = [str(c or "").strip() for c in row]
                    fecha_info = None
                    fecha_idx  = -1
                    for i in range(min(3, len(cells))):
                        fi = _parse_date(cells[i])
                        if fi:
                            fecha_info = fi
                            fecha_idx  = i
                            break
                    if not fecha_info:
                        continue
                    fecha_dt, fecha_str = fecha_info
                    desc = cells[fecha_idx + 1] if fecha_idx + 1 < len(cells) else ""
                    montos = []
                    for c in cells[fecha_idx + 1:]:
                        m = AMOUNT_RE.findall(c)
                        for sgn, val in m:
                            montos.append((sgn, _parse_amount(val)))
                    if not montos:
                        continue
                    saldo   = montos[-1][1] if len(montos) >= 1 else 0.0
                    importe = montos[-2][1] if len(montos) >= 2 else montos[0][1]
                    if len(montos) >= 3:
                        cargo = montos[-3][1]
                        abono = montos[-2][1]
                        saldo = montos[-1][1]
                        importe = abono if abono > 0 else -cargo
                    elif len(montos) == 2:
                        importe = montos[0][1] if montos[0][0] else -montos[0][1]
                        saldo   = montos[1][1]
                    key = (fecha_str, round(importe, 2))
                    if key not in seen:
                        seen.add(key)
                        page_txs.append(_make_tx(fecha_dt, fecha_str, desc, importe, saldo, banco, archivo))
            if page_txs:
                break  # usar la primera config que funcionó en esta página
        txs.extend(page_txs)
    return txs


# ══════════════════════════════════════════════════════════════
# ESTRATEGIA 2: pdfplumber – texto plano con regex BCP
# ══════════════════════════════════════════════════════════════

# Patrón principal BCP Soles (texto extraído):
# 03/11/2025  TRAN.CTAS.TERC.HK    250.00   5,100.82
# o con columnas Cargo/Abono separadas
BCP_LINE_RE = re.compile(
    r"(\d{2}[/\-]\d{2}[/\-]\d{2,4})"       # fecha
    r"\s+"
    r"([\w\s\.\-/&,ÁÉÍÓÚÑ]{3,60}?)"        # descripción (no greedy)
    r"\s+"
    r"([\d,\.]+)"                            # monto 1 (cargo o abono)
    r"(?:\s+([\d,\.]+))?"                    # monto 2 opcional (abono o saldo)
    r"(?:\s+([\d,\.]+))?"                    # monto 3 opcional (saldo)
    r"\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Monto monetario real: requiere siempre 2 decimales (850.00, 3,000.00, 1.234,56)
_M = r"\d{1,3}(?:[,\.]\d{3})*[,\.]\d{2}|\d+[,\.]\d{2}"

# Patrón con mes abreviado: DD-ENE-2026  DESCRIPCION  CARGO/ABONO  SALDO
# Cubre BCP, Scotiabank, BBVA, Interbank con fechas DD-MMM-YYYY
ABREV_DATE_RE = re.compile(
    r"(\d{1,2}[/\-][A-Za-z]{3}[\-\s]*\d{2,4})"  # fecha DD-ENE-2026
    r"\s+"
    r"([\w\s\.\-/&,ÁÉÍÓÚÑ]{2,80}?)"              # descripción
    r"\s+"
    r"(" + _M + r"|\-)"                           # monto 1 con decimales o guion
    r"(?:\s+(" + _M + r"|\-))?"                  # monto 2
    r"(?:\s+(" + _M + r"|\-))?"                  # monto 3
    r"\s*$",
    re.IGNORECASE | re.MULTILINE,
)
BCP_ABREV_RE = ABREV_DATE_RE  # alias

# Scotiabank: fecha + num_op + descripción + cargo + abono + saldo (todos con decimales)
SCOTIABANK_RE = re.compile(
    r"(\d{1,2}[/\-][A-Za-z]{3}[\-\s]*\d{2,4})"  # fecha
    r"\s+(\d{6,12})\s+"                           # num operacion (6-12 dígitos)
    r"([A-ZÁÉÍÓÚÑ][A-Z0-9ÁÉÍÓÚÑ\s\.\-/&,]{2,60}?)\s+"  # descripción
    r"(" + _M + r"|\-)\s+"                        # cargo
    r"(" + _M + r"|\-)\s+"                        # abono
    r"(" + _M + r")",                             # saldo
    re.IGNORECASE | re.MULTILINE,
)

# Scotiabank sin num_op: fecha + descripción + cargo + abono + saldo
SCOTIABANK_SHORT_RE = re.compile(
    r"(\d{1,2}[/\-][A-Za-z]{3}[\-\s]*\d{2,4})"
    r"\s+([A-ZÁÉÍÓÚÑ][A-Z0-9ÁÉÍÓÚÑ\s\.\-/&,]{2,60}?)\s+"
    r"(" + _M + r"|\-)\s+"
    r"(" + _M + r"|\-)\s+"
    r"(" + _M + r")",
    re.IGNORECASE | re.MULTILINE,
)

# Variante: fecha + num_ope + descripción + cargo + abono + saldo
BCP_FULL_RE = re.compile(
    r"(\d{2}[/\-]\d{2}[/\-]\d{2,4})"
    r"\s+(\w+)\s+"                           # num operación
    r"([A-Z][\w\s\.\-/&,]+?)\s+"            # descripción
    r"([\d,\.]+|-)\s+"                       # cargo
    r"([\d,\.]+|-)\s+"                       # abono
    r"([\d,\.]+)",                           # saldo
    re.MULTILINE,
)


def _strategy_text_regex_on_text(full_text: str, banco: str, archivo: str) -> list:
    """Aplica patrones regex sobre texto ya extraído (sin abrir PDF)."""
    txs = []

    # --- Scotiabank: fecha-mes-año + num_op + desc + cargo + abono + saldo ---
    for m in SCOTIABANK_RE.finditer(full_text):
        fi = _parse_date(m.group(1))
        if not fi:
            continue
        fecha_dt, fecha_str = fi
        desc    = m.group(3).strip()
        cargo_s = m.group(4)
        abono_s = m.group(5)
        saldo_s = m.group(6)
        cargo = _parse_amount(cargo_s) if cargo_s != "-" else 0.0
        abono = _parse_amount(abono_s) if abono_s != "-" else 0.0
        saldo = _parse_amount(saldo_s)
        importe = abono if abono > 0 else -cargo
        tx = _make_tx(fecha_dt, fecha_str, desc, importe, saldo, banco, archivo)
        tx["num_operacion"] = m.group(2)
        txs.append(tx)

    if txs:
        return txs

    # --- Scotiabank sin num_op ---
    for m in SCOTIABANK_SHORT_RE.finditer(full_text):
        fi = _parse_date(m.group(1))
        if not fi:
            continue
        fecha_dt, fecha_str = fi
        desc    = m.group(2).strip()
        cargo_s = m.group(3)
        abono_s = m.group(4)
        saldo_s = m.group(5)
        cargo = _parse_amount(cargo_s) if cargo_s != "-" else 0.0
        abono = _parse_amount(abono_s) if abono_s != "-" else 0.0
        saldo = _parse_amount(saldo_s)
        importe = abono if abono > 0 else -cargo
        txs.append(_make_tx(fecha_dt, fecha_str, desc, importe, saldo, banco, archivo))

    if txs:
        return txs

    # --- Fecha con mes abreviado sin num_op (DD-ENE-2026 desc monto saldo) ---
    for m in ABREV_DATE_RE.finditer(full_text):
        fi = _parse_date(m.group(1))
        if not fi:
            continue
        fecha_dt, fecha_str = fi
        desc = m.group(2).strip()
        def _amt(s): return _parse_amount(s) if s and s != "-" else None
        g3 = _amt(m.group(3)); g4 = _amt(m.group(4)); g5 = _amt(m.group(5))
        if g5 is not None and g3 is not None and g4 is not None:
            importe = g4 if g4 > 0 else -g3
            saldo   = g5
        elif g4 is not None and g3 is not None:
            importe, saldo = g3, g4
        elif g3 is not None:
            importe, saldo = g3, 0.0
        else:
            continue
        txs.append(_make_tx(fecha_dt, fecha_str, desc, importe, saldo, banco, archivo))

    if txs:
        return txs

    # --- Intento BCP_FULL_RE (3 montos: cargo, abono, saldo) ---
    for m in BCP_FULL_RE.finditer(full_text):
        fi = _parse_date(m.group(1))
        if not fi:
            continue
        fecha_dt, fecha_str = fi
        num_ope = m.group(2)
        desc    = m.group(3).strip()
        cargo_s = m.group(4)
        abono_s = m.group(5)
        saldo_s = m.group(6)
        cargo = _parse_amount(cargo_s) if cargo_s != "-" else 0.0
        abono = _parse_amount(abono_s) if abono_s != "-" else 0.0
        saldo = _parse_amount(saldo_s)
        importe = abono if abono > 0 else -cargo
        tx = _make_tx(fecha_dt, fecha_str, desc, importe, saldo, banco, archivo)
        tx["num_operacion"] = num_ope
        txs.append(tx)

    if txs:
        return txs

    # --- Intento BCP_LINE_RE (2-3 montos en la línea) ---
    for m in BCP_LINE_RE.finditer(full_text):
        fi = _parse_date(m.group(1))
        if not fi:
            continue
        fecha_dt, fecha_str = fi
        desc = m.group(2).strip()
        g3 = _parse_amount(m.group(3)) if m.group(3) else 0.0
        g4 = _parse_amount(m.group(4)) if m.group(4) else None
        g5 = _parse_amount(m.group(5)) if m.group(5) else None
        if g5 is not None:
            cargo, abono, saldo = g3, g4, g5
            importe = abono if abono > 0 else -cargo
        elif g4 is not None:
            importe, saldo = g3, g4
        else:
            importe, saldo = g3, 0.0
        txs.append(_make_tx(fecha_dt, fecha_str, desc, importe, saldo, banco, archivo))

    return txs


def _strategy_text_regex(pdf, banco, archivo):
    """Extrae texto con pdfplumber y delega a _strategy_text_regex_on_text."""
    full_text = ""
    for page in pdf.pages:
        t = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
        full_text += t + "\n"
    return _strategy_text_regex_on_text(full_text, banco, archivo)


# ══════════════════════════════════════════════════════════════
# ESTRATEGIA 3: Línea a línea con ventana deslizante
# ══════════════════════════════════════════════════════════════

def _strategy_sliding_window(pdf, banco, archivo):
    """
    Extrae líneas y reconstruye transacciones buscando fechas
    y asociando la descripción y montos en líneas cercanas.
    """
    txs = []
    lines = []
    for page in pdf.pages:
        text = page.extract_text() or ""
        lines.extend(text.split("\n"))

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        fi = _parse_date(line)
        if fi:
            fecha_dt, fecha_str = fi
            # Reúne hasta 3 líneas siguientes como contexto
            context = " ".join(lines[i:min(i+3, len(lines))]).strip()
            # Extrae todos los montos del contexto
            montos = AMOUNT_RE.findall(context)
            amounts = [_parse_amount(v) for _, v in montos]
            # Descripción: texto entre la fecha y el primer monto
            desc_match = re.search(
                r"\d{1,2}[/\-](?:\d{2}|[A-Za-z]{3})[/\-\s]\d{2,4}\s+(.*?)\s*\d[\d,\.]*\s*$",
                context, re.DOTALL
            )
            desc = desc_match.group(1).strip() if desc_match else line
            desc = re.sub(r"\s+", " ", desc)[:100]

            if amounts:
                saldo   = amounts[-1]
                importe = amounts[-2] if len(amounts) >= 2 else amounts[0]
                if len(amounts) >= 3:
                    cargo, abono, saldo = amounts[-3], amounts[-2], amounts[-1]
                    importe = abono if abono > 0 else -cargo
                txs.append(_make_tx(fecha_dt, fecha_str, desc, importe, saldo, banco, archivo))
                i += 2  # saltar líneas ya consumidas
                continue
        i += 1
    return txs


# ══════════════════════════════════════════════════════════════
# ESTRATEGIA 4: pypdf como último recurso
# ══════════════════════════════════════════════════════════════

def _strategy_pypdf(filepath, banco, archivo):
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    try:
        reader = PdfReader(filepath)
    except Exception:
        return []
    txs = []
    full_text = "\n".join(
        page.extract_text() or "" for page in reader.pages
    )
    for m in BCP_LINE_RE.finditer(full_text):
        fi = _parse_date(m.group(1))
        if not fi:
            continue
        fecha_dt, fecha_str = fi
        desc = m.group(2).strip()
        g3 = _parse_amount(m.group(3)) if m.group(3) else 0.0
        g4 = _parse_amount(m.group(4)) if m.group(4) else None
        saldo   = g4 if g4 is not None else 0.0
        importe = g3
        txs.append(_make_tx(fecha_dt, fecha_str, desc, importe, saldo, banco, archivo))
    return txs


# ══════════════════════════════════════════════════════════════
# ESTRATEGIA 5: Parse de texto pegado/copiado manualmente
# ══════════════════════════════════════════════════════════════

def _infer_signs(txs: list) -> list:
    """
    Infiere el signo del importe comparando saldos consecutivos.
    Si el saldo baja → importe negativo (cargo). Si sube → positivo (abono).
    Solo aplica cuando el importe viene sin signo explícito.
    """
    if len(txs) < 2:
        return txs
    for i in range(1, len(txs)):
        prev_saldo = txs[i - 1]["saldo"]
        curr_saldo = txs[i]["saldo"]
        imp        = abs(txs[i]["importe"])
        if imp == 0:
            continue
        delta = curr_saldo - prev_saldo
        # Si el delta es negativo el movimiento es un cargo
        if delta < -0.005:
            txs[i]["importe"] = -imp
        else:
            txs[i]["importe"] = imp
    return txs


def extract_from_text(raw_text: str, banco: str = "BCP SOLES") -> dict:
    """
    Procesa texto copiado directamente del PDF o del portal del banco.
    Acepta formato libre con fechas DD/MM/YYYY y montos.
    """
    txs = []
    lines = raw_text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue
        fi = _parse_date(line)
        if not fi:
            continue
        fecha_dt, fecha_str = fi

        # Montos en la línea (conserva signo explícito)
        amounts_raw = AMOUNT_RE.findall(line)
        amounts = [
            (-_parse_amount(v) if sgn == "-" else _parse_amount(v))
            for sgn, v in amounts_raw
        ]

        # Descripción: texto entre la fecha y el primer número
        desc = ""
        for pat in DATE_PATTERNS:
            m = pat.search(line)
            if m:
                after_date = line[m.end():].strip()
                tmp = after_date
                for sgn, v in amounts_raw:
                    tmp = tmp.replace(sgn + v, "", 1).replace(v, "", 1).strip()
                # Limpiar guiones y espacios sobrantes al final
                desc = re.sub(r"[\s\-]+$", "", re.sub(r"\s+", " ", tmp)).strip()[:100]
                break

        if not amounts:
            continue

        if len(amounts) >= 3:
            # Tres montos: cargo  abono  saldo
            cargo_v = amounts[-3]
            abono_v = amounts[-2]
            saldo   = amounts[-1]
            importe = abono_v if abono_v > 0 else -cargo_v
        elif len(amounts) == 2:
            # Dos montos: importe  saldo (signo se infiere después)
            importe = amounts[0]
            saldo   = amounts[1]
        else:
            importe = amounts[0]
            saldo   = 0.0

        txs.append(_make_tx(fecha_dt, fecha_str, desc or line[:80], importe, saldo, banco))

    # Inferir signos cuando solo tenemos cargo/abono como positivo
    txs = _infer_signs(txs)
    return {"transactions": txs, "total": len(txs), "strategy": "text_paste"}


# ══════════════════════════════════════════════════════════════
# ESTRATEGIA BCP DD-MM: estado de cuenta con fechas DD-MM, cargo guión final
# Ejemplo: 02-04 ... 64.00-  1,667.98   →  cargo de 64.00, saldo 1,667.98
# Año extraído del encabezado: DEL01/04/2025AL30/04/2025
# ══════════════════════════════════════════════════════════════

_BCP_DDMM_YEAR_RE = re.compile(r"DEL\s*(\d{2})/(\d{2})/(\d{4})\s*AL", re.IGNORECASE)
_BCP_DDMM_LINE_RE = re.compile(
    r"^(\d{2})-(\d{2})"            # DD-MM (día-mes)
    r"[ \t]+"
    r"(.+?)"                         # descripción (no greedy)
    r"[ \t]+"
    r"([\d,]*\.\d{2}-?)"            # importe: cargo termina en -, abono no
    r"[ \t]+"
    r"([\d,]+\.\d{2})"              # saldo
    r"[ \t]*$",
    re.MULTILINE,
)


def _fix_bcp_date_anomalies(txs: list) -> list:
    """
    Corrige transacciones donde FECHA_PROC ≠ FECHA_VALOR en estados BCP.
    El PDF muestra fecha_proc, pero la continuidad del saldo indica fecha_valor.
    Regla: si txs[i].fecha > txs[i-1].fecha Y txs[i+1].fecha <= txs[i-1].fecha
           → reclasificar txs[i] a la fecha de txs[i-1].
    Ejemplo: 26-04 (164.00-) → 27-04 (175.00-) → 26-04 (2,510.00-)
             El 175.00- es valor 26-04 aunque proceso 27-04.
    """
    if len(txs) < 3:
        return txs
    for i in range(1, len(txs) - 1):
        prev_f = txs[i - 1]["fecha_operacion"]
        curr_f = txs[i]["fecha_operacion"]
        next_f = txs[i + 1]["fecha_operacion"]
        if curr_f > prev_f and next_f <= prev_f:
            # Reclasificar: usar fecha del bloque anterior
            prev_tx = txs[i - 1]
            txs[i]["fecha_operacion"] = prev_f
            txs[i]["fecha"]           = prev_f
            txs[i]["periodo"]         = prev_f[:7]
            txs[i]["mes"]             = prev_tx["mes"]
    return txs


def _strategy_bcp_ddmm(full_text: str, banco: str, archivo: str) -> list:
    """
    Parser BCP Perú: estado de cuenta con fechas DD-MM (sin año).
    - Año extraído de encabezado 'DEL01/04/2025AL30/04/2025'
    - Cargo (débito): monto con guión final  → 64.00-
    - Abono (crédito): monto sin guión       → 7,290.00
    - Montos pequeños de tipo .10- (ITF) también soportados
    - Última columna de cada línea es el saldo corriente
    - Aplica corrección de fecha PROC→VALOR por continuidad de saldo
    """
    ym = _BCP_DDMM_YEAR_RE.search(full_text)
    year = int(ym.group(3)) if ym else datetime.now().year

    txs  = []
    seen = set()

    for m in _BCP_DDMM_LINE_RE.finditer(full_text):
        dd     = int(m.group(1))
        mm_num = int(m.group(2))
        desc_raw  = m.group(3).strip()
        amt_str   = m.group(4)
        saldo_str = m.group(5)

        try:
            fecha_dt  = datetime(year, mm_num, dd)
            fecha_iso = fecha_dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

        is_cargo  = amt_str.endswith("-")
        amt_clean = amt_str.rstrip("-")
        if amt_clean.startswith("."):          # .10 → 0.10
            amt_clean = "0" + amt_clean
        amt = _parse_amount(amt_clean)
        saldo = _parse_amount(saldo_str)

        importe = -amt if is_cargo else amt
        desc = re.sub(r"\s+", " ", desc_raw)[:120]

        key = (fecha_iso, round(importe, 2), round(saldo, 2))
        if key not in seen:
            seen.add(key)
            txs.append(_make_tx(fecha_dt, fecha_iso, desc, importe, saldo, banco, archivo))

    # Corregir anomalías de fecha PROC vs VALOR
    txs = _fix_bcp_date_anomalies(txs)
    return txs


# ══════════════════════════════════════════════════════════════
# ESTRATEGIA SCOTIABANK PERÚ: formato DD/MM DD/MM COD DESC REF AMT SALDO
# ══════════════════════════════════════════════════════════════

# Patrón de línea: dos fechas cortas + código + descripción + referencia + montos
_SCOT_LINE = re.compile(
    r"^(\d{2}/\d{2})\s+"          # fecha oper DD/MM
    r"\d{2}/\d{2}\s+"             # fecha valor (ignorar)
    r"\d{2,3}\s+"                 # código operación (001, 784, 928...)
    r"(.+?)\s+"                   # descripción + referencia (todo el medio)
    r"(\d[\d,]*\.\d{2})"          # monto (cargo o abono)
    r"(?:\s+(\d[\d,.]*\.\d{2}))?$",  # saldo (opcional)
    re.MULTILINE | re.IGNORECASE,
)

# Patrón para detectar año del documento: "Desde 01-ENE-2026"
_YEAR_RE  = re.compile(r"Desde\s+\d{1,2}[\-/][A-Za-z]{3}[\-/\s]+(\d{4})", re.IGNORECASE)
# Patrón para saldo inicial: "Saldo Final al 31 de Diciembre del 2025 8.29"
_SALDO_INICIAL_RE = re.compile(
    r"Saldo\s+Final\s+al\s+\d+\s+de\s+\w+\s+del?\s+\d{4}\s+([\d,]+\.\d{2})",
    re.IGNORECASE,
)


def _strategy_scotiabank(full_text: str, banco: str, archivo: str) -> list:
    """
    Parser específico Scotiabank Perú.
    Línea: DD/MM  DD/MM  COD  CONCEPTO  REFERENCIA  MONTO  SALDO
    Detecta el año del encabezado y usa _infer_signs para cargo/abono.
    """
    # Detectar año del documento
    ym = _YEAR_RE.search(full_text)
    year = int(ym.group(1)) if ym else datetime.now().year

    # Saldo inicial (última línea de "Saldo Final" antes de las transacciones)
    saldo_previo = 0.0
    for sm in _SALDO_INICIAL_RE.finditer(full_text):
        saldo_previo = _parse_amount(sm.group(1))
        break  # solo el primero (al inicio del período)

    txs  = []
    seen = set()

    for m in _SCOT_LINE.finditer(full_text):
        fecha_short = m.group(1)      # "02/01"
        middle      = m.group(2).strip()
        amt_str     = m.group(3)      # monto (cargo o abono)
        saldo_str   = m.group(4)      # saldo

        # Parsear fecha DD/MM + año detectado
        try:
            dd, mm_num = map(int, fecha_short.split("/"))
            fecha_dt  = datetime(year, mm_num, dd)
            fecha_iso = fecha_dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue

        # Separar referencia (último token) de descripción
        parts = middle.rsplit(None, 1)
        desc = parts[0].strip()[:100] if len(parts) == 2 else middle[:100]
        ref  = parts[1].strip()      if len(parts) == 2 else ""

        amt   = _parse_amount(amt_str)
        saldo = _parse_amount(saldo_str) if saldo_str else 0.0

        # Importe siempre positivo aquí; _infer_signs lo corregirá
        importe = amt

        key = (fecha_iso, round(amt, 2), round(saldo, 2))
        if key in seen:
            continue
        seen.add(key)

        tx = _make_tx(fecha_dt, fecha_iso, desc, importe, saldo, banco, archivo)
        tx["num_operacion"] = ref
        txs.append(tx)

    if not txs:
        return txs

    # Inferir signo de la primera transacción usando saldo inicial
    if saldo_previo > 0:
        delta0 = txs[0]["saldo"] - saldo_previo
        txs[0]["importe"] = abs(txs[0]["importe"]) if delta0 >= 0 else -abs(txs[0]["importe"])

    return _infer_signs(txs)


# ══════════════════════════════════════════════════════════════
# ESTRATEGIA 5: Extracción por coordenadas (X/Y) con pdfplumber
# Funciona con PDFs donde el texto no está en líneas continuas.
# Lee cada palabra con su posición, agrupa por fila (Y) y columna (X).
# ══════════════════════════════════════════════════════════════

def _strategy_coords(pdf, banco, archivo):
    """
    Usa las coordenadas de cada palabra para reconstruir filas y columnas.
    Procesa TODAS las páginas del PDF.
    """
    txs = []
    seen = set()
    Y_TOLERANCE = 4

    for page in pdf.pages:
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
        if not words:
            continue

        # Agrupar palabras por fila (Y cercano)
        rows_dict = {}
        for w in words:
            y_key = round(w["top"] / Y_TOLERANCE) * Y_TOLERANCE
            if y_key not in rows_dict:
                rows_dict[y_key] = []
            rows_dict[y_key].append(w)

        for y_key in sorted(rows_dict):
            row_words = sorted(rows_dict[y_key], key=lambda w: w["x0"])
            row_text  = " ".join(w["text"] for w in row_words)

            # La fila debe contener una fecha
            fi = _parse_date(row_text)
            if not fi:
                continue
            fecha_dt, fecha_str = fi

            # Montos: todas las palabras que son números en la fila
            amounts_raw = AMOUNT_RE.findall(row_text)
            if not amounts_raw:
                continue
            amounts = [
                (-_parse_amount(v) if sgn == "-" else _parse_amount(v))
                for sgn, v in amounts_raw
            ]

            # Descripción: texto entre la fecha y el primer monto
            desc = ""
            m = re.search(r"\d{2}[/\-]\d{2}[/\-]\d{2,4}\s+(.*?)\s*[\d,\.]{4,}", row_text)
            if m:
                desc = re.sub(r"\s+", " ", m.group(1)).strip()[:100]
            if not desc:
                desc = row_text[:80]

            if len(amounts) >= 3:
                importe = amounts[-2] if amounts[-2] != 0 else -amounts[-3]
                saldo   = amounts[-1]
            elif len(amounts) == 2:
                importe = amounts[0]
                saldo   = amounts[1]
            else:
                importe = amounts[0]
                saldo   = 0.0

            key = (fecha_str, round(amounts[-1], 2) if amounts else 0)
            if key not in seen:
                seen.add(key)
                txs.append(_make_tx(fecha_dt, fecha_str, desc, importe, saldo, banco, archivo))

    return txs


# ══════════════════════════════════════════════════════════════
# ESTRATEGIA 6: Línea a línea con regex muy permisivo
# Último recurso: captura cualquier línea que tenga fecha + número
# Procesa TODAS las páginas.
# ══════════════════════════════════════════════════════════════

def _strategy_any_line(pdf, banco, archivo):
    """Captura cualquier línea con fecha y al menos un número — todas las páginas."""
    txs = []
    seen = set()
    for page in pdf.pages:
        text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
        for line in text.split("\n"):
            line = line.strip()
            if len(line) < 10:
                continue
            fi = _parse_date(line)
            if not fi:
                continue
            fecha_dt, fecha_str = fi
            amounts_raw = AMOUNT_RE.findall(line)
            if not amounts_raw:
                continue
            amounts = [
                (-_parse_amount(v) if sgn == "-" else _parse_amount(v))
                for sgn, v in amounts_raw
            ]
            # Descripción: todo entre la fecha y el primer monto
            m = re.search(r"\d{2}[/\-]\d{2}[/\-]\d{2,4}\s*(.*)", line)
            rest = m.group(1).strip() if m else line
            for sgn, v in amounts_raw:
                rest = rest.replace(sgn + v, "").replace(v, "")
            desc = re.sub(r"\s+", " ", rest).strip()[:100]

            if len(amounts) >= 3:
                saldo   = amounts[-1]
                importe = amounts[-2] if amounts[-2] != 0 else -amounts[-3]
            elif len(amounts) == 2:
                importe, saldo = amounts[0], amounts[1]
            else:
                importe, saldo = amounts[0], 0.0

            key = (fecha_str, round(saldo, 2))
            if key not in seen:
                seen.add(key)
                txs.append(_make_tx(fecha_dt, fecha_str, desc or "SIN DESC", importe, saldo, banco, archivo))
    return txs


# ══════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════

def extract_bcp_soles(pdf_path: str, banco: str = "BCP SOLES") -> dict:
    """
    Extrae transacciones de un PDF bancario usando 4 estrategias en cascada.
    Devuelve {'transactions': [...], 'total': N, 'strategy': 'nombre'} o
             {'error': '...', 'transactions': [], 'debug': '...'}
    """
    archivo = pdf_path

    try:
        import pdfplumber
    except ImportError:
        return {"error": "pdfplumber no instalado. Ejecuta: pip3 install pdfplumber",
                "transactions": []}

    debug_info = []
    full_txt = ""

    # ── Ruta rápida: pypdf primero (3-5× más veloz que pdfplumber) ───────────
    try:
        from pypdf import PdfReader
        _reader = PdfReader(pdf_path)
        _pypdf_text = "\n".join(p.extract_text() or "" for p in _reader.pages)
        if _pypdf_text.strip():
            full_txt = _pypdf_text
            try:
                txs = _strategy_scotiabank(_pypdf_text, banco, archivo)
                debug_info.append(f"pypdf+scotiabank: {len(txs)}")
                if len(txs) >= 2:
                    return {"transactions": txs, "total": len(txs),
                            "strategy": "pypdf+scotiabank", "raw_text": _pypdf_text}
            except Exception as _e:
                debug_info.append(f"pypdf+scotiabank falló: {_e}")
            try:
                txs = _strategy_text_regex_on_text(_pypdf_text, banco, archivo)
                debug_info.append(f"pypdf+text_regex: {len(txs)}")
                if len(txs) >= 2:
                    return {"transactions": txs, "total": len(txs),
                            "strategy": "pypdf+text_regex", "raw_text": _pypdf_text}
            except Exception as _e:
                debug_info.append(f"pypdf+text_regex falló: {_e}")
            try:
                txs = _strategy_bcp_ddmm(_pypdf_text, banco, archivo)
                debug_info.append(f"pypdf+bcp_ddmm: {len(txs)}")
                if len(txs) >= 2:
                    return {"transactions": txs, "total": len(txs),
                            "strategy": "pypdf+bcp_ddmm", "raw_text": _pypdf_text}
            except Exception as _e:
                debug_info.append(f"pypdf+bcp_ddmm falló: {_e}")
    except Exception as _e:
        debug_info.append(f"pypdf falló: {_e}")

    # ── Fallback: pdfplumber (soporta PDFs complejos, tablas, etc.) ──────────
    try:
        with pdfplumber.open(pdf_path) as pdf:
            num_pages = len(pdf.pages)
            debug_info.append(f"PDF: {num_pages} págs")

            # Extraer texto completo UNA VEZ para reutilizar en estrategias de texto
            try:
                full_txt = "\n".join(
                    page.extract_text(x_tolerance=2, y_tolerance=2) or ""
                    for page in pdf.pages
                )
            except Exception:
                full_txt = ""

            # ── Scotiabank (texto ya extraído, sin costo extra) ──
            try:
                txs = _strategy_scotiabank(full_txt, banco, archivo)
                debug_info.append(f"Scotiabank: {len(txs)}")
                if len(txs) >= 2:
                    return {"transactions": txs, "total": len(txs),
                            "strategy": "scotiabank", "raw_text": full_txt}
            except Exception as e:
                debug_info.append(f"Scotiabank falló: {e}")

            # ── BCP DD-MM (fechas sin año, cargo con guión final) ──
            try:
                txs = _strategy_bcp_ddmm(full_txt, banco, archivo)
                debug_info.append(f"BCP_DDMM: {len(txs)}")
                if len(txs) >= 2:
                    return {"transactions": txs, "total": len(txs),
                            "strategy": "bcp_ddmm", "raw_text": full_txt}
            except Exception as e:
                debug_info.append(f"BCP_DDMM falló: {e}")

            # ── Estrategia 1: Regex sobre texto (rápida) ─────
            try:
                txs = _strategy_text_regex(pdf, banco, archivo)
                debug_info.append(f"Regex: {len(txs)}")
                if len(txs) >= 2:
                    return {"transactions": txs, "total": len(txs),
                            "strategy": "text_regex", "raw_text": full_txt}
            except Exception as e:
                debug_info.append(f"Regex falló: {e}")

            # ── Estrategia 2: Ventana deslizante (rápida) ────
            try:
                txs = _strategy_sliding_window(pdf, banco, archivo)
                debug_info.append(f"Sliding: {len(txs)}")
                if len(txs) >= 2:
                    return {"transactions": txs, "total": len(txs),
                            "strategy": "sliding_window", "raw_text": full_txt}
            except Exception as e:
                debug_info.append(f"Sliding falló: {e}")

            # ── Estrategia 3: Coordenadas X/Y ────────────────
            try:
                txs = _strategy_coords(pdf, banco, archivo)
                debug_info.append(f"Coords: {len(txs)}")
                if len(txs) >= 2:
                    txs = _infer_signs(txs)
                    return {"transactions": txs, "total": len(txs),
                            "strategy": "coords", "raw_text": full_txt}
            except Exception as e:
                debug_info.append(f"Coords falló: {e}")

            # ── Estrategia 4: Cualquier línea fecha+número ───
            try:
                txs = _strategy_any_line(pdf, banco, archivo)
                debug_info.append(f"Any_line: {len(txs)}")
                if len(txs) >= 2:
                    txs = _infer_signs(txs)
                    return {"transactions": txs, "total": len(txs),
                            "strategy": "any_line", "raw_text": full_txt}
            except Exception as e:
                debug_info.append(f"Any_line falló: {e}")

            # ── Estrategia 5: Tablas (lenta — último recurso) ─
            try:
                txs = _strategy_tables(pdf, banco, archivo)
                debug_info.append(f"Tables: {len(txs)}")
                if len(txs) >= 2:
                    return {"transactions": txs, "total": len(txs),
                            "strategy": "tables", "raw_text": full_txt}
            except Exception as e:
                debug_info.append(f"Tables falló: {e}")

    except Exception as e:
        debug_info.append(f"No se pudo abrir el PDF: {e}")

    return {
        "transactions": [], "total": 0, "strategy": "none",
        "error": "No se pudieron extraer transacciones. Usa la opción 'Pegar texto del PDF'.",
        "debug": " | ".join(debug_info),
        "raw_text": full_txt,
    }


# ══════════════════════════════════════════════════════════════
# EXTRACCIÓN DE TEXTO CRUDO PARA FALLBACK
# ══════════════════════════════════════════════════════════════

def extract_raw_text(pdf_path: str) -> str:
    """
    Devuelve el texto completo extraído por pdfplumber.
    Se usa como fallback cuando las estrategias automáticas fallan:
    el texto se pre-llena en el textarea para que el usuario procese
    con la estrategia text_paste sin copiar nada manualmente.
    """
    text_parts = []
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text(x_tolerance=3, y_tolerance=3)
                if t:
                    text_parts.append(t)
        if text_parts:
            return "\n".join(text_parts)
    except Exception:
        pass

    # Segundo intento: pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    except Exception:
        pass

    return "\n".join(text_parts)


# ══════════════════════════════════════════════════════════════
# IMPORTACIÓN DESDE EXCEL (template VIVA CONT)
# ══════════════════════════════════════════════════════════════

def extract_from_excel(file_path: str) -> dict:
    """Importa transacciones desde un Excel con el formato del template VIVA CONT."""
    import pandas as pd
    import math

    def safe(v):
        if v is None:
            return ""
        try:
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return ""
        except Exception:
            pass
        s = str(v).strip()
        return "" if s in ("nan", "None", "NaT") else s

    def safe_float(v):
        try:
            f = float(v)
            return 0.0 if math.isnan(f) or math.isinf(f) else f
        except (TypeError, ValueError):
            return 0.0

    try:
        df = pd.read_excel(file_path, header=1, dtype=str)
        df = df.dropna(how="all").reset_index(drop=True)

        # Pad to 21 columns so position access is safe
        while len(df.columns) < 21:
            df[f"_pad{len(df.columns)}"] = ""

        # Vectorized column extraction
        c = df.iloc
        col = lambda i: df.iloc[:, i].fillna("").astype(str).str.strip()

        fecha_ops   = col(0)
        descrips    = col(9)

        _INVALIDOS = {"", "0", "nan", "None", "NaT", "00:00:00"}
        mask = ~(fecha_ops.isin(_INVALIDOS) | (fecha_ops == ""))
        df = df[mask].reset_index(drop=True)

        records = []
        for i in range(len(df)):
            r = df.iloc[i]
            def g(pos): return safe(r.iloc[pos] if pos < len(r) else "")
            moneda = g(2) or "PEN"
            if moneda in ("nan", "None", "NaT", ""): moneda = "PEN"
            tipo = g(11) or g(10)
            desc = g(9)
            records.append({
                "fecha_operacion":   g(0),
                "referencia":        g(1),
                "moneda":            moneda,
                "importe":           safe_float(r.iloc[3] if 3 < len(r) else 0),
                "num_operacion":     g(4),
                "periodo":           g(5),
                "banco":             g(6),
                "fecha":             g(7),
                "mes":               g(8),
                "descripcion":       desc,
                "tipo":              tipo if tipo not in ("", "nan") else _detect_tipo(desc),
                "detalle":           g(12) or desc,
                "op":                g(13),
                "tipo_doc":          g(14),
                "ruc":               g(15),
                "cliente_proveedor": g(16),
                "num_documento":     g(17),
                "saldo":             safe_float(r.iloc[18] if 18 < len(r) else 0),
                "doc_cont":          g(19),
                "comprobante":       g(20) if len(r) > 20 else "",
                "archivo_origen":    file_path,
            })
        return {"transactions": records, "total": len(records)}
    except Exception as e:
        return {"error": str(e), "transactions": []}
