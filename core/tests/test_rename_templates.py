import pytest

from genesis_core.rename.templates import (
    RenameTemplateError,
    render_template,
    sanitize_filename_component,
)


def test_sanitize_replaces_forbidden_characters():
    assert sanitize_filename_component('AC/DC: "Back" in Black?') == "AC DC Back in Black"


def test_sanitize_strips_trailing_dots_and_spaces():
    assert sanitize_filename_component("Test.  ") == "Test"


def test_sanitize_handles_reserved_windows_names():
    assert sanitize_filename_component("CON") == "_CON"
    assert sanitize_filename_component("con") == "_con"


def test_sanitize_truncates_very_long_values():
    long_value = "A" * 500
    assert len(sanitize_filename_component(long_value)) == 180


def test_render_template_empty_numeric_field_does_not_crash():
    """Regressionstest: fehlende Tracknummer + numerischer Format-Spec
    (':02d') darf nicht mit 'Unknown format code' crashen, sondern muss zu
    einem leeren String werden (Prinzip #16 - keine Fantasiedaten)."""
    rendered, empty = render_template(
        "{track:02d} - {title}.{ext}",
        {
            "artist": None, "albumartist": None, "album": None,
            "title": "Nur Titel", "track": None, "disc": None,
            "year": None, "ext": "mp3", "original_filename": "x",
        },
    )
    assert rendered == " - Nur Titel.mp3"
    assert "track" in empty


def test_render_template_basic_substitution():
    rendered, empty = render_template(
        "{track:02d} - {title}.{ext}",
        {"track": 3, "title": "Enter Sandman", "ext": "flac"},
    )
    assert rendered == "03 - Enter Sandman.flac"
    assert empty == []


def test_render_template_reports_empty_fields_without_fabricating_text():
    rendered, empty = render_template(
        "{artist} - {title}.{ext}",
        {"artist": None, "title": "Enter Sandman", "ext": "mp3"},
    )
    assert rendered == " - Enter Sandman.mp3"
    assert empty == ["artist"]


def test_render_template_sanitizes_forbidden_characters_in_values():
    rendered, _ = render_template(
        "{artist} - {title}.{ext}",
        {"artist": "AC/DC", "title": "T:N:T", "ext": "mp3"},
    )
    assert "/" not in rendered.split(".mp3")[0].replace(" - ", "")
    assert rendered == "AC DC - T N T.mp3"


def test_render_template_unknown_placeholder_raises_clear_error():
    with pytest.raises(RenameTemplateError, match="nicht_existent"):
        render_template("{nicht_existent}.{ext}", {"ext": "mp3"})


def test_render_template_invalid_format_spec_raises_clear_error():
    with pytest.raises(RenameTemplateError):
        render_template("{track:02d}.{ext}", {"track": "not-a-number", "ext": "mp3"})


def test_render_template_strips_trailing_dot_for_extensionless_file():
    """Deep-Review-Fund (Sitzung 3, Haertung): Ist die Original-Datei ohne
    Endung (also `{ext}` leer) und die Vorlage endet trotzdem mit
    ".{ext}", entstuende ohne Fix ein Dateiname mit trailendem Punkt
    (z.B. "Titel."), was unter Windows zu Normalisierungs-Ueberraschungen
    fuehren kann. Muss wie ein ganz normaler sanitisierter Platzhalterwert
    behandelt werden (vgl. test_sanitize_strips_trailing_dots_and_spaces)."""
    rendered, empty_fields = render_template(
        "{title}.{ext}", {"title": "Titel", "ext": ""}
    )
    assert rendered == "Titel"
    assert not rendered.endswith(".")
    assert empty_fields == ["ext"]


def test_render_template_does_not_strip_legitimate_trailing_extension():
    """Gegenprobe: ein ganz normaler, vorhandener Dateiname darf durch den
    neuen rstrip-Schritt nicht veraendert werden."""
    rendered, _ = render_template("{title}.{ext}", {"title": "Titel", "ext": "mp3"})
    assert rendered == "Titel.mp3"
