"""Regressionstests für die Funde aus Deep-Review-Sitzung 13 (vollständiger
Neu-Durchlauf über alle Komponenten, siehe `docs/REVIEW_LOG.md` /
`PROGRESS.md`).

Gefundene und hier abgesicherte Fehler in `genesis_ui/api_client.py`:

1. `F821` (ruff): `get_cutter_waveform_bytes()`, `export_chapters_text()`
   und `get_voice_synthesis_audio()` riefen bei einem HTTP-Fehlerstatus
   eine nicht existierende Funktion `_extract_detail(exc)` auf. Das führte
   zu einem `NameError` ANSTATT der erwarteten `GenesisAPIError` - der
   Nutzer hätte bei jedem Server-Fehler auf diesen drei Endpunkten einen
   unerwarteten Absturz/Crash-Dialog gesehen statt einer sauberen,
   lesbaren Fehlermeldung mit evtl. Fehler-ID. Fix: alle drei Stellen
   rufen jetzt - wie die übrigen Methoden auch - den tatsächlich
   existierenden Helper `_build_api_error(exc)` auf.
2. `F811` (ruff): Zwei Definitionen von `list_jobs` in `GenesisAPIClient`
   (eine ohne, eine mit `limit`-Parameter) - die zweite überschrieb die
   erste vollständig (toter Code). Fix: die tote erste Definition wurde
   entfernt.

Läuft OHNE Qt/PySide6 (reiner `httpx`-Client-Test, kein GUI-Code), damit
diese Tests auch ohne Display-Server garantiert laufen.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from genesis_ui.api_client import GenesisAPIClient, GenesisAPIError


def _client_with_transport(handler) -> GenesisAPIClient:
    """Baut einen `GenesisAPIClient`, dessen interner `httpx.Client` auf
    einen `MockTransport` umgeleitet wurde - kein echter Netzwerkzugriff
    nötig, exakt derselbe Code-Pfad wie im echten Betrieb."""
    client = GenesisAPIClient(base_url="http://testserver")
    client._client = httpx.Client(
        base_url="http://testserver", transport=httpx.MockTransport(handler)
    )
    return client


@pytest.mark.parametrize(
    "method_name, call_args, call_kwargs",
    [
        ("get_cutter_waveform_bytes", (1,), {}),
        ("export_chapters_text", (1,), {"fmt": "txt"}),
        ("get_voice_synthesis_audio", (1,), {}),
    ],
)
def test_binary_text_endpoints_raise_proper_api_error_on_http_error(
    method_name: str, call_args: tuple, call_kwargs: dict
):
    """Vorher: `NameError: name '_extract_detail' is not defined` statt
    einer `GenesisAPIError` - die eigentliche Fehlerursache wurde
    verschluckt und durch einen Folgefehler ersetzt."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"detail": "Medium nicht gefunden"},
            request=request,
        )

    client = _client_with_transport(handler)
    method = getattr(client, method_name)

    with pytest.raises(GenesisAPIError) as exc_info:
        method(*call_args, **call_kwargs)

    assert "Medium nicht gefunden" in str(exc_info.value)


def test_binary_endpoint_preserves_error_id_from_global_handler():
    """Stellt sicher, dass auch das zweite Fehlerformat (§37, echter
    unerwarteter Fehler mit `error_id`/`solution_hint`) korrekt
    durchgereicht wird - genau das, was `_build_api_error` leistet und
    `_extract_detail` (nie existent) nicht leisten konnte."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={
                "error_id": "ERR-1234",
                "message": "Unerwarteter Fehler beim Waveform-Rendering",
                "solution_hint": "Erneut versuchen",
            },
            request=request,
        )

    client = _client_with_transport(handler)

    with pytest.raises(GenesisAPIError) as exc_info:
        client.get_cutter_waveform_bytes(1)

    assert exc_info.value.error_id == "ERR-1234"
    assert exc_info.value.solution_hint == "Erneut versuchen"


def test_list_jobs_has_exactly_one_definition_with_limit_parameter():
    """Vorher gab es ZWEI `list_jobs`-Methoden in derselben Klasse; Python
    behält bei Klassenattributen immer nur die zuletzt definierte, die
    erste (ohne `limit`) war toter, nie erreichbarer Code. Dieser Test
    stellt sicher, dass die verbleibende Methode weiterhin wie erwartet
    funktioniert (inkl. `limit`-Parameter, der von
    `job_queue_view.py` tatsächlich verwendet wird)."""
    captured_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, json=[], request=request)

    client = _client_with_transport(handler)
    result = client.list_jobs(limit=100)

    assert result == []
    assert captured_params.get("limit") == "100"
