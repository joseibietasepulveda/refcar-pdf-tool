#!/usr/bin/env bash
# Doble clic en este archivo para ejecutar la herramienta web (macOS).

set -e
cd "$(dirname "$0")"

# Prioriza Anaconda/Conda si está instalado, luego Homebrew y sistema
export PATH="/opt/anaconda3/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_LIBRARY_PATH:-}"

KEY_FILE="MI_OPENROUTER_KEY.txt"
TEMPLATE="Plantilla_OpenRouter_Key.txt"

if [[ ! -f "$KEY_FILE" ]]; then
  if [[ -f "$TEMPLATE" ]]; then
    cp "$TEMPLATE" "$KEY_FILE"
    open -t "$KEY_FILE" 2>/dev/null || true
    echo ""
    echo "Se creó $KEY_FILE con instrucciones."
    echo "Pega tu API key de OpenRouter, guarda el archivo y vuelve a hacer doble clic en el lanzador."
    echo ""
    read -r -p "Presiona ENTER para cerrar..."
    exit 0
  fi
fi

PYTHON="$(command -v python3 || true)"
if [[ -z "$PYTHON" ]]; then
  echo "No se encontró python3. Instálalo desde https://www.python.org o con Homebrew: brew install python"
  echo ""
  read -r -p "Presiona ENTER para cerrar..."
  exit 1
fi

if ! "$PYTHON" -m pip show streamlit >/dev/null 2>&1; then
  echo "Instalando dependencias (solo la primera vez)..."
  "$PYTHON" -m pip install -r "$(pwd)/requirements.txt"
fi

# Si hay clave en el archivo .txt y no en el entorno, config.py también la puede leer;
# export opcional como respaldo ante dotenv viejo sin key.
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY}"
if grep -qi "sk-or-v1-" "$KEY_FILE" 2>/dev/null; then
  line="$(grep -m1 -o 'sk-or-v1-[^[:space:]]*' "$KEY_FILE" 2>/dev/null || true)"
  if [[ -n "$line" ]] && [[ -z "${OPENROUTER_API_KEY}" ]]; then
    export OPENROUTER_API_KEY="$line"
  fi
fi

STREAMLIT_PORT=8501

free_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti "tcp:${port}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "Puerto ${port} en uso. Cerrando instancia anterior..."
    # shellcheck disable=SC2086
    kill ${pids} 2>/dev/null || true
    sleep 0.4
    pids="$(lsof -ti "tcp:${port}" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      # shellcheck disable=SC2086
      kill -9 ${pids} 2>/dev/null || true
      sleep 0.2
    fi
  fi
}

free_port "$STREAMLIT_PORT"

echo "Abriendo herramienta web en http://localhost:${STREAMLIT_PORT} ..."
if ! "$PYTHON" -m streamlit run web_app.py --server.port "$STREAMLIT_PORT" --browser.gatherUsageStats false; then
  CODE=$?
else
  CODE=0
fi

echo ""
read -r -p "Presiona ENTER para cerrar..."
exit "$CODE"
