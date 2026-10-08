using System;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Threading;

namespace GenesisMediaManager.Client;

public partial class App : Application
{
    // KRITISCHER FUND (echter Nutzer-Testlauf, erste jemals erfolgte reale
    // Ausfuehrung dieses Clients ueberhaupt - WPF kann in der Linux-
    // Entwicklungssandbox nur GEBAUT, nie AUSGEFUEHRT werden): Diese Klasse
    // hatte frueher kein eigenes OnStartup und App.xaml setzte stattdessen
    // "StartupUri=\"MainWindow.xaml\"". WPFs StartupUri-Mechanismus erzeugt
    // das Fenster intern per Reflection mit einem PARAMETERLOSEN
    // Konstruktor - MainWindow hat aber ausschliesslich
    // "MainWindow(string apiBaseUrl = ...)" (ein C#-Standardparameter
    // erzeugt KEINEN echten parameterlosen Konstruktor auf IL-Ebene). Das
    // fuehrte zu einer MissingMethodException direkt beim Programmstart -
    // auf JEDEM Rechner, bei JEDEM Start, ausnahmslos. Sichtbares Symptom:
    // ein Fenster "blitzt kurz auf und schliesst sich sofort wieder".
    //
    // Fix: MainWindow wird jetzt explizit in OnStartup erzeugt (kein
    // StartupUri mehr noetig/vorhanden). Zusaetzlich (Prinzip "kein
    // stiller Fehlschlag", §37): globale Exception-Handler, die JEDE
    // unbehandelte Ausnahme in eine sichtbare Fehlermeldung UND eine
    // Log-Datei schreiben, statt den Prozess kommentarlos zu beenden -
    // genau das fehlte bisher komplett und machte die Fehlersuche fuer
    // den Nutzer unmoeglich.
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        DispatcherUnhandledException += OnDispatcherUnhandledException;
        AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;
        TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;

        try
        {
            var window = new MainWindow();
            window.Show();
        }
        catch (Exception ex)
        {
            ReportFatalError("Starten des Hauptfensters", ex);
            Shutdown(-1);
        }
    }

    private void OnDispatcherUnhandledException(object? sender, DispatcherUnhandledExceptionEventArgs e)
    {
        ReportFatalError("UI-Thread (unbehandelte Ausnahme)", e.Exception);
        // Handled = true verhindert, dass Windows zusaetzlich noch seinen
        // eigenen (unuebersetzten, technischen) Absturz-Dialog zeigt -
        // unsere eigene, klare Meldung wurde in ReportFatalError bereits
        // angezeigt. Die App wird danach trotzdem beendet (sauberer
        // Zustand ist nach einer unerwarteten Ausnahme nicht garantiert).
        e.Handled = true;
        Shutdown(-1);
    }

    private void OnUnhandledException(object? sender, UnhandledExceptionEventArgs e)
    {
        if (e.ExceptionObject is Exception ex)
        {
            ReportFatalError("Hintergrund-Thread (unbehandelte Ausnahme)", ex);
        }
    }

    private void OnUnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs e)
    {
        ReportFatalError("Hintergrundaufgabe (nicht abgefangene Ausnahme)", e.Exception);
        e.SetObserved();
    }

    /// <summary>
    /// Schreibt die Ausnahme in eine Log-Datei unter
    /// "%APPDATA%\GenesisMediaManager\client-crash.log" (dieselbe
    /// Datenablage wie api_token.txt, siehe GenesisApiClient) UND zeigt
    /// eine deutschsprachige MessageBox, damit ein Absturz niemals mehr
    /// unbemerkt/stumm bleibt. Faengt selbst wiederum alle Fehler beim
    /// Schreiben/Anzeigen ab - ein Fehler in der Fehlerbehandlung darf
    /// nicht zu einer zweiten, noch verwirrenderen Ausnahme fuehren.
    /// </summary>
    private static void ReportFatalError(string context, Exception ex)
    {
        try
        {
            var dataDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "GenesisMediaManager");
            Directory.CreateDirectory(dataDir);
            var logPath = Path.Combine(dataDir, "client-crash.log");
            var entry = new StringBuilder()
                .AppendLine($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] Kontext: {context}")
                .AppendLine(ex.ToString())
                .AppendLine(new string('-', 80))
                .ToString();
            File.AppendAllText(logPath, entry, Encoding.UTF8);

            MessageBox.Show(
                $"GENESIS Media Manager ist auf einen unerwarteten Fehler gestossen und muss beendet werden.\n\n" +
                $"Kontext: {context}\n" +
                $"Fehler: {ex.Message}\n\n" +
                $"Details wurden gespeichert in:\n{logPath}\n\n" +
                "Bitte diese Datei bei einer Fehlermeldung mit angeben.",
                "GENESIS Media Manager - Fehler",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
        catch
        {
            // Bewusst verschluckt: wenn schon das Fehlerprotokollieren
            // selbst fehlschlaegt (z.B. kein Schreibzugriff), soll
            // trotzdem nicht ein zweiter, verwirrenderer Crash entstehen.
        }
    }
}
