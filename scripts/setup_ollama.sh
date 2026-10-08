#!/usr/bin/env bash
# Richtet die lokale KI (Ollama) für GENESIS ein. Siehe DECISIONS.md ADR-0003.
# Muss ggf. erneut ausgeführt werden, da ~/.ollama (Modelldateien) nicht Teil
# des Workspace-Snapshots ist.
set -euo pipefail

MODEL="${1:-qwen2.5:0.5b}"

if ! command -v ollama >/dev/null 2>&1; then
  echo ">>> Installiere Ollama ..."
  sudo apt-get update -qq && sudo apt-get install -y -qq zstd
  curl -fsSL https://ollama.com/install.sh -o /tmp/ollama_install.sh
  sudo sh /tmp/ollama_install.sh
fi

if ! curl -s -m 2 http://127.0.0.1:11434/api/version >/dev/null 2>&1; then
  echo ">>> Starte Ollama-Dienst ..."
  sudo systemctl start ollama 2>/dev/null || (nohup ollama serve >/tmp/ollama.log 2>&1 &)
  sleep 2
fi

echo ">>> Ziehe Modell: $MODEL (klein, offline-fähig) ..."
ollama pull "$MODEL"

echo ">>> Teste Modell ..."
# Deep-Review-Fund (Sitzung 2, Profil Bash/POSIX): der JSON-Body wurde zuvor
# per Shell-String-Interpolation von $MODEL zusammengebaut - ein $MODEL-Wert
# mit Anführungszeichen/Backslash haette ungueltiges JSON erzeugt. Fix:
# JSON sicher via python3 -c/json.dumps erzeugen statt String-Interpolation.
REQUEST_BODY="$(MODEL="$MODEL" python3 -c '
import json, os
print(json.dumps({
    "model": os.environ["MODEL"],
    "prompt": "Sag Hallo in einem Wort.",
    "stream": False,
}))
')"
curl -s http://127.0.0.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d "$REQUEST_BODY" \
  | python3 -c "import json,sys; print('Antwort:', json.load(sys.stdin).get('response','(keine Antwort)'))"

echo ">>> Ollama einsatzbereit unter http://127.0.0.1:11434 (Modell: $MODEL)"
