// Tests fuer ApiErrorSupport.BuildApiErrorText (Gap L, §37) und das
// §37-Fehlerformat-Parsing in GenesisApiClient.BuildApiExceptionFromBody -
// Erwartungswerte 1:1 aus error_dialog.py::show_api_error() bzw.
// api_client.py::_build_api_error() der Python-Referenz abgeleitet.
using GenesisMediaManager.Client.Api;
using Xunit;

namespace GenesisMediaManager.Client.Tests;

public class ApiErrorSupportTests
{
    [Fact]
    public void MessageOnlyStaysUntouched()
    {
        Assert.Equal(
            "Speichern fehlgeschlagen: X",
            ApiErrorSupport.BuildApiErrorText("Speichern fehlgeschlagen: X", null, null));
    }

    [Fact]
    public void ErrorIdLineIsAppendedAfterBlankLine()
    {
        // Python: text += "\n\n" + tr("error_dialog.error_id_line", ...)
        Assert.Equal(
            "Fehler\n\nFehler-ID: E-123 (im Fehler-Center nachschlagbar)",
            ApiErrorSupport.BuildApiErrorText(
                "Fehler", "Fehler-ID: E-123 (im Fehler-Center nachschlagbar)", null));
    }

    [Fact]
    public void SolutionHintLineIsAppendedWithSingleNewline()
    {
        // Python: text += "\n" + tr("error_dialog.solution_hint_line", ...)
        Assert.Equal(
            "Fehler\nHinweis: Bitte erneut versuchen.",
            ApiErrorSupport.BuildApiErrorText("Fehler", null, "Hinweis: Bitte erneut versuchen."));
    }

    [Fact]
    public void BothLinesKeepPythonOrder()
    {
        Assert.Equal(
            "Fehler\n\nFehler-ID: E-1\nHinweis: Erneut versuchen.",
            ApiErrorSupport.BuildApiErrorText("Fehler", "Fehler-ID: E-1", "Hinweis: Erneut versuchen."));
    }

    [Fact]
    public void EmptyLinesAreIgnoredLikePythonTruthiness()
    {
        // Python prueft "if exc.error_id:" - leerer String zaehlt als fehlend.
        Assert.Equal("Fehler", ApiErrorSupport.BuildApiErrorText("Fehler", "", ""));
    }

    [Fact]
    public void GlobalExceptionHandlerFormatIsParsed()
    {
        // §37-Format 2: error_id-Schluessel entscheidet, message/solution_hint
        // werden uebernommen (Vorrang vor "detail" wie in _build_api_error).
        var ex = GenesisApiClient.BuildApiExceptionFromBody(
            "{\"error_id\": \"E-2026-1\", \"message\": \"Ein unerwarteter Fehler ist aufgetreten.\", "
                + "\"solution_hint\": \"Bitte erneut versuchen.\", \"detail\": \"ignoriert\"}",
            500, "Internal Server Error");
        Assert.Equal("Ein unerwarteter Fehler ist aufgetreten.", ex.Message);
        Assert.Equal("E-2026-1", ex.ErrorId);
        Assert.Equal("Bitte erneut versuchen.", ex.SolutionHint);
    }

    [Fact]
    public void GlobalExceptionHandlerFormatWithoutMessageFallsBackToStatusCode()
    {
        var ex = GenesisApiClient.BuildApiExceptionFromBody(
            "{\"error_id\": \"E-1\", \"solution_hint\": null}", 500, "Internal Server Error");
        Assert.Contains("500", ex.Message);
        Assert.Equal("E-1", ex.ErrorId);
        Assert.Null(ex.SolutionHint);
    }

    [Fact]
    public void ValidationDetailFormatIsParsed()
    {
        // §37-Format 1: FastAPI-HTTPException mit "detail".
        var ex = GenesisApiClient.BuildApiExceptionFromBody(
            "{\"detail\": \"Medium nicht gefunden\"}", 404, "Not Found");
        Assert.Equal("Medium nicht gefunden", ex.Message);
        Assert.Null(ex.ErrorId);
        Assert.Null(ex.SolutionHint);
    }

    [Fact]
    public void NonJsonBodyFallsBackToStatusCodeText()
    {
        var ex = GenesisApiClient.BuildApiExceptionFromBody("<html>Fehler</html>", 502, "Bad Gateway");
        Assert.Contains("502", ex.Message);
        Assert.Null(ex.ErrorId);
    }

    [Fact]
    public void EmptyBodyFallsBackToStatusCodeText()
    {
        var ex = GenesisApiClient.BuildApiExceptionFromBody("", 500, "Internal Server Error");
        Assert.Contains("500", ex.Message);
        Assert.Null(ex.ErrorId);
    }
}
