"""Voice-Studio-Engine: Profilverwaltung + Sprachsynthese (§28/§29, ADR-0018).

Sicherheitsmechanik (Prinzip #4/#5/#6/#17, §44), analog zu den anderen
Apply-Fluessen des Projekts:
1. Profile anlegen/loeschen und jede Sprachsynthese sind "Aenderungen" und
   erfordern IMMER `confirm=True` - auch wenn kein bestehendes Original
   veraendert wird (es entsteht jedes Mal eine NEUE Audiodatei/Zeile).
2. Das Loeschen eines Voice-Profils ist unwiderruflich (die Historie
   vergangener Syntheseergebnisse haengt per Cascade daran) - dafuer gilt
   die VERSCHAERFTE Bestaetigung aus dem Originalauftrag ("Loeschen=extra
   confirm"): zusaetzlich zu `confirm=True` muss der Aufrufer den exakten
   Profilnamen wiederholen (`confirm_name`), sonst wird abgelehnt.
3. Eine optionale Referenz-Sprachprobe (`sample_path`) wird beim Loeschen
   NIE von der Festplatte entfernt - nur die Datenbankzeile verschwindet
   (Prinzip #4: Originaldateien werden nie automatisch geloescht).
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from genesis_core.audio_formats import spec_for_name
from genesis_core.convert.ffmpeg_convert import FFmpegConvertError, render_conversion
from genesis_core.db.models import VoiceProfile, VoiceSynthesis
from genesis_core.logutil import get_logger
from genesis_core.voice.base import TTSProvider, TTSProviderUnavailableError

log = get_logger("VoiceEngine")

# §28 "Voice Profile testen" - feste, kurze Testsaetze pro Sprache. Rein
# informativ/neutral gehalten (kein personenbezogener Inhalt).
TEST_PHRASES: dict[str, str] = {
    "de": "Dies ist eine Testaufnahme des GENESIS Voice Studio.",
    "en": "This is a test recording from the GENESIS Voice Studio.",
    "ja": "これは GENESIS Voice Studio のテスト録音です。",
    "ru": "Это тестовая запись из GENESIS Voice Studio.",
}
DEFAULT_TEST_PHRASE = TEST_PHRASES["en"]


class VoiceProfileNotFoundError(ValueError):
    pass


class VoiceApplyNotConfirmedError(PermissionError):
    """Wird geworfen, wenn eine Aenderung ohne `confirm=True` versucht wird
    (Prinzip #17/§44, hart im Code erzwungen)."""


class VoiceDeleteNotConfirmedError(PermissionError):
    """Verschaerfte Bestaetigung fuers Loeschen (§28/Prinzip #6: "Loeschen
    = extra confirm") - `confirm_name` muss exakt dem Profilnamen
    entsprechen."""


class VoiceSynthesisError(RuntimeError):
    """Die eigentliche Sprachsynthese ist fehlgeschlagen - wird NIE
    stillschweigend verschluckt (Prinzip #19/§37)."""


@dataclasses.dataclass
class VoiceProfileInput:
    name: str
    engine: str
    model_path: str | None = None
    language: str | None = None
    description: str | None = None
    model_license: str | None = None
    offline_capable: bool = True
    open_source: bool = True
    commercial_use_allowed: bool | None = None
    sample_path: str | None = None


def create_voice_profile(
    db: Session, data: VoiceProfileInput, *, confirm: bool
) -> VoiceProfile:
    if not confirm:
        raise VoiceApplyNotConfirmedError(
            "confirm=True erforderlich - das Anlegen eines Voice-Profils ist "
            "eine Aenderung (Prinzip #17)."
        )
    if not data.name.strip():
        raise ValueError("Der Profilname darf nicht leer sein.")
    existing = db.execute(
        select(VoiceProfile).where(VoiceProfile.name == data.name)
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError(f"Ein Voice-Profil mit dem Namen '{data.name}' existiert bereits.")

    profile = VoiceProfile(
        name=data.name,
        engine=data.engine,
        model_path=data.model_path,
        language=data.language,
        description=data.description,
        model_license=data.model_license,
        offline_capable=data.offline_capable,
        open_source=data.open_source,
        commercial_use_allowed=data.commercial_use_allowed,
        sample_path=data.sample_path,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    log.info("Voice-Profil angelegt: id=%s name=%s engine=%s", profile.id, profile.name, profile.engine)
    return profile


def list_voice_profiles(db: Session) -> list[VoiceProfile]:
    return list(db.execute(select(VoiceProfile).order_by(VoiceProfile.name)).scalars())


def get_voice_profile(db: Session, profile_id: int) -> VoiceProfile | None:
    return db.get(VoiceProfile, profile_id)


def delete_voice_profile(
    db: Session, profile_id: int, *, confirm: bool, confirm_name: str | None
) -> None:
    profile = db.get(VoiceProfile, profile_id)
    if profile is None:
        raise VoiceProfileNotFoundError(f"Voice-Profil {profile_id} nicht gefunden")
    if not confirm:
        raise VoiceApplyNotConfirmedError(
            "confirm=True erforderlich - das Loeschen eines Voice-Profils ist "
            "eine Aenderung (Prinzip #17)."
        )
    if confirm_name != profile.name:
        raise VoiceDeleteNotConfirmedError(
            "Loeschen eines Voice-Profils erfordert die exakte Wiederholung "
            "des Profilnamens in 'confirm_name' (zusaetzliche Sicherung bei "
            "unwiderruflichen Aktionen, §28/Prinzip #6)."
        )
    log.info("Voice-Profil geloescht: id=%s name=%s", profile.id, profile.name)
    db.delete(profile)
    db.commit()


def _render_export(tmp_wav_path: Path, export_format: str) -> Path:
    """Konvertiert die rohe Piper-WAV-Ausgabe bei Bedarf in das gewuenschte
    Zielformat (MP3/FLAC/...). Bei export_format=='wav' wird die Datei
    unveraendert gelassen (kein unnoetiger Zusatzschritt)."""
    if export_format == "wav":
        return tmp_wav_path
    spec = spec_for_name(export_format)
    final_path = tmp_wav_path.with_suffix(spec.extension)
    try:
        render_conversion(
            tmp_wav_path, final_path, codec_args=list(spec.ffmpeg_codec_args)
        )
    except FFmpegConvertError as exc:
        raise VoiceSynthesisError(str(exc)) from exc
    finally:
        # Die rohe Zwischen-WAV ist kein Nutzerdokument, sondern reiner
        # Syntheseabfall unseres eigenen Pipeline-Schritts - darf im
        # Unterschied zu Originaldateien geraeumt werden (Prinzip #4 gilt
        # fuer Originale/bestehende Nutzerdateien, nicht fuer selbst erzeugte
        # Zwischenergebnisse).
        if final_path.exists() and tmp_wav_path.exists() and tmp_wav_path != final_path:
            tmp_wav_path.unlink()
    return final_path


def synthesize_text(
    db: Session,
    provider: TTSProvider,
    profile_id: int,
    text: str,
    *,
    output_dir: Path,
    export_format: str = "wav",
    confirm: bool,
    is_test_phrase: bool = False,
) -> VoiceSynthesis:
    if not confirm:
        raise VoiceApplyNotConfirmedError(
            "confirm=True erforderlich - jede Sprachsynthese erzeugt eine "
            "neue Audiodatei und braucht eine explizite Nutzerbestaetigung."
        )
    profile = db.get(VoiceProfile, profile_id)
    if profile is None:
        raise VoiceProfileNotFoundError(f"Voice-Profil {profile_id} nicht gefunden")
    if not text.strip():
        raise ValueError("Der zu sprechende Text darf nicht leer sein.")

    output_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:8]
    timestamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%S")
    tmp_wav_path = output_dir / f"voice_{profile_id}_{timestamp}_{token}.wav"

    try:
        result = provider.synthesize(
            text, model_path=profile.model_path, output_wav_path=str(tmp_wav_path)
        )
    except TTSProviderUnavailableError:
        raise
    except Exception as exc:  # pragma: no cover - defensiv, siehe Prinzip #19
        raise VoiceSynthesisError(f"Sprachsynthese fehlgeschlagen: {exc}") from exc

    final_path = _render_export(Path(result.output_path), export_format)

    row = VoiceSynthesis(
        voice_profile_id=profile.id,
        text=text,
        output_path=str(final_path),
        export_format=export_format,
        duration_seconds=result.duration_seconds,
        sample_rate=result.sample_rate,
        engine=result.engine_name,
        is_test_phrase=is_test_phrase,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log.info(
        "Sprachsynthese gespeichert: profile=%s format=%s dauer=%.2fs -> %s",
        profile.id, export_format, result.duration_seconds, final_path,
    )
    return row


def list_syntheses(db: Session, profile_id: int | None = None) -> list[VoiceSynthesis]:
    stmt = select(VoiceSynthesis).order_by(VoiceSynthesis.created_at.desc())
    if profile_id is not None:
        stmt = stmt.where(VoiceSynthesis.voice_profile_id == profile_id)
    return list(db.execute(stmt).scalars())


def get_synthesis(db: Session, synthesis_id: int) -> VoiceSynthesis | None:
    return db.get(VoiceSynthesis, synthesis_id)


def get_test_phrase_for_language(language: str | None) -> str:
    if language and language.lower()[:2] in TEST_PHRASES:
        return TEST_PHRASES[language.lower()[:2]]
    return DEFAULT_TEST_PHRASE
