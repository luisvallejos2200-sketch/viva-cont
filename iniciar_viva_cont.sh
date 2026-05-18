#!/bin/bash
# ── VIVA CONT – Script de inicio ──────────────────────────────

PYTHON=$(which python3 2>/dev/null || echo "/Library/Developer/CommandLineTools/usr/bin/python3")
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=5050
URL="http://localhost:$PORT"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║         VIVA CONT v1.0 – Iniciando...        ║"
echo "║         Viva Consulting Empresas S.A.C.       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Check Python
if [ -z "$PYTHON" ]; then
  echo "❌ Python3 no encontrado. Instálalo desde python.org"
  exit 1
fi

# Check Flask
$PYTHON -c "import flask" 2>/dev/null || {
  echo "📦 Instalando dependencias..."
  pip3 install flask flask-cors pdfplumber pandas openpyxl pypdf
}

echo "🚀 Iniciando servidor en $URL"
echo "   Presiona Ctrl+C para detener"
echo ""

cd "$SCRIPT_DIR"
$PYTHON app.py &
SERVER_PID=$!

# Open browser after 1.5 seconds
sleep 1.5
open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null

# Wait for server
wait $SERVER_PID
