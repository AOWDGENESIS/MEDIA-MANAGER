#!/usr/bin/env python3
"""Minimales Beispiel fuer §29 "Eigene Stimme fuer andere Programme".

Demonstriert konkret die im Originalauftrag skizzierte Architektur:

    Andere lokale Anwendung
            |
    GENESIS Voice API   <- genau diese bereits bestehenden REST-Endpunkte
            |               (/voice/profiles, /voice/profiles/{id}/synthesize)
    Voice Engine        <- austauschbar (aktuell: Piper), siehe ADR-0018
            |
          Audio

Dieses Skript ist selbst KEIN Teil der GENESIS-Hauptanwendung - es simuliert
eine EXTERNE lokale Anwendung, die GENESIS rein ueber die bereits
dokumentierte lokale REST-API (127.0.0.1, Shared-Secret-Token) als
TTS-Dienst nutzt, ohne irgendeinen GENESIS-internen Code zu importieren.

Nutzung:
    python3 scripts/genesis_voice_cli.py --list
    python3 scripts/genesis_voice_cli.py --profile 1 --text "Hallo Welt" \\
        --format mp3 --out out.mp3

Die vier Pflichtangaben aus §28 (Engine/Lizenz/Offline/Open-Source) werden
vor jeder Synthese angezeigt - eine externe Anwendung bekommt dieselbe
Transparenz wie die GENESIS-Oberflaeche selbst.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Dieses Beispielskript benoetigt 'httpx' (pip install httpx).", file=sys.stderr)
    sys.exit(1)


def _default_data_dir() -> Path:
    env_override = os.environ.get("GENESIS_DATA_DIR")
    if env_override:
        return Path(env_override).expanduser()
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "GenesisMediaManager"
    return Path.home() / ".genesis-media-manager"


def _read_token() -> str | None:
    token_path = _default_data_dir() / "api_token.txt"
    if not token_path.exists():
        return None
    return token_path.read_text(encoding="utf-8").strip() or None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8420")
    parser.add_argument("--list", action="store_true", help="Alle Voice-Profile auflisten")
    parser.add_argument("--profile", type=int, help="ID des zu nutzenden Voice-Profils")
    parser.add_argument("--text", help="Zu sprechender Text")
    parser.add_argument("--format", default="wav", choices=("wav", "mp3", "flac"))
    parser.add_argument("--out", help="Zieldatei fuer den Audio-Export")
    args = parser.parse_args()

    token = _read_token()
    headers = {"X-Genesis-Token": token} if token else {}
    client = httpx.Client(base_url=args.base_url, headers=headers, timeout=60.0)

    status = client.get("/voice/status").json()
    print(
        f"GENESIS Voice API: provider={status['provider']} "
        f"local={status['is_local']} internet={status['requires_internet']} "
        f"available={status['available']}"
    )
    if not status["available"]:
        print("Keine lokale TTS-Engine verfuegbar - Abbruch.", file=sys.stderr)
        return 1

    profiles = client.get("/voice/profiles").json()["profiles"]
    if args.list or args.profile is None:
        print("\nVerfuegbare Voice-Profile:")
        for p in profiles:
            print(
                f"  [{p['id']}] {p['name']} - Engine={p['engine']} "
                f"Lizenz={p['model_license']} Offline={p['offline_capable']} "
                f"OpenSource={p['open_source']} "
                f"Kommerziell={p['commercial_use_allowed']}"
            )
        if args.profile is None:
            return 0

    if not args.text:
        print("--text ist erforderlich, wenn --profile angegeben ist.", file=sys.stderr)
        return 1

    profile = next((p for p in profiles if p["id"] == args.profile), None)
    if profile is None:
        print(f"Profil {args.profile} nicht gefunden.", file=sys.stderr)
        return 1

    print(
        f"\nNutze Profil '{profile['name']}' (Engine={profile['engine']}, "
        f"Lizenz={profile['model_license']}, Offline={profile['offline_capable']}, "
        f"OpenSource={profile['open_source']}, "
        f"Kommerziell={profile['commercial_use_allowed']}) ..."
    )

    resp = client.post(
        f"/voice/profiles/{args.profile}/synthesize",
        json={"text": args.text, "export_format": args.format, "confirm": True},
    )
    resp.raise_for_status()
    synthesis = resp.json()["synthesis"]
    print(json.dumps(synthesis, indent=2, ensure_ascii=False))

    source_path = Path(synthesis["output_path"])
    if args.out:
        Path(args.out).write_bytes(source_path.read_bytes())
        print(f"Audio gespeichert unter: {args.out}")
    else:
        print(f"Audio liegt lokal unter: {source_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
