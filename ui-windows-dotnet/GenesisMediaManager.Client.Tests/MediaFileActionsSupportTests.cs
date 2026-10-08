// Tests fuer MediaFileActions/MediaSearchFiltersSupport
// (MediaFileActionsSupport.cs). Beide Klassen lagen urspruenglich
// "versteckt" am Kopf der ansonsten WPF-abhaengigen
// MainWindow.MediaFilters.cs und hatten deshalb trotz fehlender
// WPF-Abhaengigkeit bislang KEINE Testabdeckung (gefunden im Deep-Search
// nach "mache alle noch fehlenden tests") - nach Extraktion in eine
// eigene Datei hier nachgeholt.
//
// MediaFileActions.TryOpenPath hat einen echten Seiteneffekt im
// Erfolgsfall (startet einen externen OS-Prozess ueber
// Process.Start(UseShellExecute: true), z.B. den Standard-Dateimanager/
// -Player). Dieser Erfolgspfad wird hier bewusst NICHT getestet (keine
// echten externen Prozesse aus der Unit-Test-Suite heraus starten,
// Ergebnis waere zudem plattform-/umgebungsabhaengig). Getestet werden
// die deterministischen Schutzklauseln, die den Grossteil der Methode
// ausmachen: leerer/Whitespace-Pfad, nicht existierende Datei, nicht
// existierendes Verzeichnis - jeweils mit garantiertem false als
// Rueckgabe, unabhaengig vom Betriebssystem.
namespace GenesisMediaManager.Client.Tests;

public class MediaFileActionsSupportTests
{
    [Fact]
    public void TryOpenPath_EmptyPath_ReturnsFalse()
    {
        Assert.False(MediaFileActions.TryOpenPath("", revealContainingFolder: false));
    }

    [Fact]
    public void TryOpenPath_WhitespacePath_ReturnsFalse()
    {
        Assert.False(MediaFileActions.TryOpenPath("   ", revealContainingFolder: false));
    }

    [Fact]
    public void TryOpenPath_NonExistentFile_ReturnsFalse()
    {
        var missing = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "genesis-does-not-exist-12345.flac");
        Assert.False(MediaFileActions.TryOpenPath(missing, revealContainingFolder: false));
    }

    [Fact]
    public void TryOpenPath_RevealContainingFolder_NonExistentDirectory_ReturnsFalse()
    {
        var missingFileInMissingDir = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "genesis-does-not-exist-dir-12345", "x.flac");
        Assert.False(MediaFileActions.TryOpenPath(missingFileInMissingDir, revealContainingFolder: true));
    }

    [Fact]
    public void TryOpenPath_RevealContainingFolder_ExistingParentOfNonExistentFile_DoesNotThrow()
    {
        // GetDirectoryName(path) wird aufgeloest, OHNE dass die Datei
        // selbst existieren muss (nur der Ordner wird geprueft/geoeffnet) -
        // Temp-Verzeichnis existiert garantiert, daher darf hier keine
        // Ausnahme nach aussen dringen (Grundprinzip #16), unabhaengig
        // davon, ob der zugrunde liegende Process.Start-Aufruf in dieser
        // Sandbox tatsaechlich einen Handler findet.
        var fileInExistingDir = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "genesis-maybe-missing.flac");
        var exception = Record.Exception(() => MediaFileActions.TryOpenPath(fileInExistingDir, revealContainingFolder: true));
        Assert.Null(exception);
    }

    // --- MediaSearchFiltersSupport.Empty ------------------------------------

    [Fact]
    public void Empty_EqualsDefaultConstructedMediaSearchFilters()
    {
        // Record-Werte-Gleichheit: die Sentinel-Instanz muss exakt so
        // behandelt werden wie ein frisch angelegtes "kein Filter gesetzt"
        // (siehe MainWindow.xaml.cs::ShowMediaTableAsync, das per == gegen
        // dieses Feld vergleicht, um auf null zu normalisieren).
        Assert.Equal(new MediaSearchFilters(), MediaSearchFiltersSupport.Empty);
    }

    [Fact]
    public void Empty_HasNoActiveFilters()
    {
        Assert.Equal(0, MediaSearchFiltersSupport.Empty.CountActive());
    }

    [Fact]
    public void Empty_ProducesEmptyQueryString()
    {
        Assert.Equal(string.Empty, MediaSearchFiltersSupport.Empty.ToQueryString());
    }
}
