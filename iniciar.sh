#!/usr/bin/env bash
# Enciende el asistente en Mac (o Linux): Ollama, la API y la consola, y abre la consola.
# Uso:  ./iniciar.sh        Para apagarlo: Ctrl+C en esta terminal.
# Equivale a iniciar.bat de Windows. La instalación en Mac está en docs/instalacion.md.
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "Falta instalar. Sigue la sección de Mac en docs/instalacion.md."
  exit 1
fi

responde() { curl -s -o /dev/null --max-time 3 "$1"; }

if ! responde http://127.0.0.1:11434/api/tags; then
  echo "Abriendo Ollama..."
  if [ -d "/Applications/Ollama.app" ]; then open -a Ollama; else (ollama serve >/dev/null 2>&1 &); fi
  for _ in $(seq 1 30); do responde http://127.0.0.1:11434/api/tags && break; sleep 1; done
  responde http://127.0.0.1:11434/api/tags || { echo "Ollama no respondió. Ábrelo a mano y vuelve a intentar."; exit 1; }
fi

if responde http://127.0.0.1:8000/health; then
  echo "El asistente ya estaba encendido."
else
  echo "Encendiendo la API y la consola..."
  "$PY" -m uvicorn app.api:app --port 8000 &
  API=$!
  "$PY" -m streamlit run app/consola.py --server.port 8501 --server.headless true &
  CONSOLA=$!
  trap 'echo; echo "Apagando..."; kill $API $CONSOLA 2>/dev/null' INT TERM EXIT
  for _ in $(seq 1 90); do responde http://127.0.0.1:8000/health && break; sleep 1; done
  responde http://127.0.0.1:8000/health || { echo "La API no respondió; revisa los mensajes de arriba."; exit 1; }
fi

echo
echo "Consola:  http://localhost:8501"
echo "Avatar:   http://localhost:8000/avatar/"
command -v open >/dev/null && open http://localhost:8501
wait
