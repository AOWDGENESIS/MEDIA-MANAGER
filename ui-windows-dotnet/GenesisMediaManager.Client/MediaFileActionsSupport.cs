// WPF-unabhaengige Hilfslogik rund um den Medientabellen-Filterdialog und
// "Datei/Ordner oeffnen" (Gap K, siebter inkrementeller Schritt). Beide
// Klassen lagen urspruenglich am Kopf von MainWindow.MediaFilters.cs (das
// im uebrigen Teil den eigentlichen, WPF-abhaengigen Filterdialog via
// Window/ScrollViewer/GroupBox aufbaut) - hierher ausgelagert, damit sie
// wie die anderen "*Support"-Klassen (MediaCoverSupport.cs,
// MediaTableSupport.cs, SettingsViewSupport.cs, ProvidersViewSupport.cs,
// LibraryBrowserSupport.cs) im reinen net8.0-Testprojekt ohne
// Windows-Targeting-Pack verlinkt und unabhaengig getestet werden koennen
// (gefunden im Deep-Search: beide Klassen hatten bislang trotz fehlender
// WPF-Abhaengigkeit KEINE Testabdeckung, weil sie "versteckt" in einer
// ansonsten WPF-abhaengigen Datei lagen).
using System;
using System.Diagnostics;
using System.IO;

namespace GenesisMediaManager.Client;

/// <summary>
/// Gap K, siebter inkrementeller Schritt - Pendant zu
/// ui-reference-pyside/genesis_ui/views/media_table.py::open_path_in_os
/// (§8/§61 "Datei oeffnen"/"Ordner oeffnen", Gap-Analyse E). Rein lesend/
/// anzeigend (Grundprinzip #4/#5) - veraendert und loescht nichts, daher
/// ohne Bestaetigungsdialog nutzbar. Liefert <c>false</c> statt zu werfen,
/// wenn das Ziel nicht existiert oder keine Standardanwendung registriert
/// ist - kein Fehler des Programms selbst, muss dem Nutzer nur gemeldet
/// werden (siehe Aufrufer in MainWindow.xaml.cs).
/// </summary>
public static class MediaFileActions
{
    public static bool TryOpenPath(string path, bool revealContainingFolder)
    {
        try
        {
            var target = revealContainingFolder ? Path.GetDirectoryName(path) : path;
            if (string.IsNullOrWhiteSpace(target)) return false;
            if (revealContainingFolder)
            {
                if (!Directory.Exists(target)) return false;
            }
            else
            {
                if (!File.Exists(target)) return false;
            }
            Process.Start(new ProcessStartInfo(target) { UseShellExecute = true });
            return true;
        }
        catch (Exception)
        {
            // Kein registrierter Handler/keine Berechtigung o.ae. - dem
            // Nutzer gemeldet statt die App abstuerzen zu lassen
            // (Grundprinzip #16).
            return false;
        }
    }
}

/// <summary>Stellt die "leer"-Referenzinstanz bereit, gegen die der
/// Rueckgabewert des Filterdialogs verglichen wird (siehe
/// MainWindow.xaml.cs::ShowMediaTableAsync - ein vom Nutzer per "OK" ohne
/// jede Eingabe bestaetigter Dialog soll denselben Effekt wie "kein Filter
/// gesetzt" haben, also <c>activeFilters = null</c>).</summary>
public static class MediaSearchFiltersSupport
{
    public static readonly MediaSearchFilters Empty = new();
}
