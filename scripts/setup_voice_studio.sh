#!/usr/bin/env bash
# Richtet lokale Testmodelle fuer das Voice Studio (Piper-TTS, §28/§29) ein.
# Siehe DECISIONS.md ADR-0018.
#
# Muss ggf. zu Beginn JEDER neuen Sandbox-Sitzung erneut ausgefuehrt werden,
# da Dateien ausserhalb von /home/user (hier bewusst /opt, siehe
# PROGRESS.md "Ressourcen-Disziplin") nicht Teil des Workspace-Snapshots
# sind. piper-tts selbst wird bereits ueber core/requirements.txt
# installiert (scripts/setup_python_env.sh) - dieses Skript laedt nur die
# (bewusst NICHT committeten, da gross + separat lizenziert) Stimmmodelle.
set -euo pipefail

VOICES_DIR="${GENESIS_PIPER_TEST_VOICES_DIR:-/opt/piper_voices}"

if [ ! -d "$VOICES_DIR" ]; then
  sudo mkdir -p "$VOICES_DIR"
  sudo chown "$(whoami):$(whoami)" "$VOICES_DIR"
fi

fetch() {
  local name="$1"
  local url_base="$2"
  if [ ! -f "$VOICES_DIR/$name.onnx" ]; then
    echo ">>> Lade Stimme: $name ..."
    curl -fsSL -o "$VOICES_DIR/$name.onnx" "$url_base/$name.onnx"
    curl -fsSL -o "$VOICES_DIR/$name.onnx.json" "$url_base/$name.onnx.json"
  else
    echo ">>> Stimme bereits vorhanden: $name"
  fi
}

# Zwei kleine Testmodelle aus dem oeffentlichen rhasspy/piper-voices-Repository
# (Hugging Face, Gewichte MIT-lizenziert - siehe ADR-0018 fuer die volle
# Lizenzkette Engine(GPL-3.0)/Gewichte(MIT)/Trainingsdaten).
fetch "de_DE-thorsten-low" "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/low"
fetch "en_US-amy-low" "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/low"

echo ""
echo ">>> Teste deutsche Stimme ..."
python3 - "$VOICES_DIR" << 'PYEOF'
import sys, wave
from piper import PiperVoice

voices_dir = sys.argv[1]
voice = PiperVoice.load(f"{voices_dir}/de_DE-thorsten-low.onnx", config_path=f"{voices_dir}/de_DE-thorsten-low.onnx.json")
with wave.open("/tmp/genesis_voice_setup_check.wav", "wb") as wav_file:
    voice.synthesize_wav("Voice Studio Testsynthese erfolgreich.", wav_file)
print("OK - Audiodatei erzeugt: /tmp/genesis_voice_setup_check.wav")
PYEOF

echo ""
echo ">>> Voice Studio einsatzbereit. Testmodelle liegen unter: $VOICES_DIR"
echo "    (de_DE-thorsten-low, en_US-amy-low)"
