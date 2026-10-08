// Reine Hilfslogik der Cover-Vorschau im Medientabellen-Detailpanel
// (MainWindow.xaml.cs::ShowMediaTableAsync), bewusst OHNE jede WPF-
// Abhaengigkeit ausgelagert (gleiches Muster wie MediaTableSupport.cs) -
// nur so kann GenesisMediaManager.Client.Tests (reines net8.0) diese Logik
// ohne echten WPF-Control-Baum/ohne System.Windows.Media.Imaging testen.
//
// §8/§22/§59 "COVER" (Gap-Analyse D) - Pendant zu
// ui-reference-pyside/genesis_ui/views/media_table.py::
// pixmap_from_artwork_bytes. Qt's QPixmap.loadFromData() entscheidet dort
// ueber einen tatsaechlichen Decodierversuch, ob Bytes ein darstellbares
// Bild sind; in .NET uebernimmt das WPF-seitig BitmapImage.EndInit(), das
// bei kaputten Daten eine Exception wirft. Diese reine Vorab-Pruefung
// (Signatur-/Magic-Bytes der gaengigen Rasterformate) ist eine bewusste,
// dokumentierte Vereinfachung gegenueber einem echten Decodierversuch: sie
// erkennt eindeutig invalide/fremde Daten VOR dem WPF-Aufruf, erspart damit
// den exception-getriebenen Kontrollfluss in MainWindow.xaml.cs und bleibt
// ohne WPF-Referenz testbar. Ein tatsaechlich beschaedigtes Bild MIT
// korrektem Dateikopf faellt weiterhin ueber den try/catch um
// BitmapImage.EndInit() auf den "kein Cover"-Platzhalter zurueck - siehe
// Kommentar dort.
namespace GenesisMediaManager.Client;

public static class MediaCoverSupport
{
    /// <summary>
    /// Liefert <c>true</c>, wenn <paramref name="data"/> mit der Signatur
    /// eines gaengigen Rasterbildformats beginnt (PNG/JPEG/GIF/BMP/WEBP) -
    /// also eine plausible Grundlage fuer einen Decodierversuch ist. Leere/
    /// <c>null</c>/zu kurze Daten liefern konsequent <c>false</c> (kein
    /// erfundenes Platzhalterbild, Grundprinzip "keine erfundenen
    /// Informationen").
    /// </summary>
    public static bool LooksLikeDecodableImage(byte[]? data)
    {
        if (data is null || data.Length < 4) return false;

        // PNG: 89 50 4E 47
        if (data[0] == 0x89 && data[1] == 0x50 && data[2] == 0x4E && data[3] == 0x47) return true;

        // JPEG: FF D8
        if (data[0] == 0xFF && data[1] == 0xD8) return true;

        // GIF: "GIF8"
        if (data.Length >= 4 && data[0] == 0x47 && data[1] == 0x49 && data[2] == 0x46 && data[3] == 0x38) return true;

        // BMP: "BM"
        if (data[0] == 0x42 && data[1] == 0x4D) return true;

        // WEBP: "RIFF" .... "WEBP"
        if (data.Length >= 12 &&
            data[0] == 0x52 && data[1] == 0x49 && data[2] == 0x46 && data[3] == 0x46 &&
            data[8] == 0x57 && data[9] == 0x45 && data[10] == 0x42 && data[11] == 0x50)
        {
            return true;
        }

        return false;
    }
}
