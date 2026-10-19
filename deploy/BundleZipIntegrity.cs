// Streaming-Integritaetspruefung fuer innere Paket-ZIPs und das aeussere
// GitHub-Downloadartefakt. Vollstaendige Dekompression, Laenge und CRC32
// pro Datei; keine Daten in GB-Groesse im Arbeitsspeicher halten.
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;

public static class BundleZipIntegrity
{
    private static readonly uint[] Table = MakeTable();

    private static uint[] MakeTable()
    {
        var table = new uint[256];
        for (uint i = 0; i < 256; i++)
        {
            uint value = i;
            for (int bit = 0; bit < 8; bit++)
                value = (value & 1) == 0 ? value >> 1 : (value >> 1) ^ 0xedb88320u;
            table[i] = value;
        }
        return table;
    }

    public static int Check(string path, string[] required)
    {
        // Windows-Dateisysteme sind nicht case-sensitive: kollidierende
        // Eintraege bereits VOR einer Extraktion konsequent ablehnen.
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        int files = 0;
        using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
        using (var zip = new ZipArchive(stream, ZipArchiveMode.Read))
        {
            foreach (var entry in zip.Entries)
            {
                string name = entry.FullName;
                if (name.StartsWith("/", StringComparison.Ordinal) || name.Contains("\\") ||
                    name.IndexOf(':') >= 0 || Array.IndexOf(name.Split('/'), "..") >= 0 ||
                    !names.Add(name))
                    throw new InvalidDataException("Unsicherer/doppelter ZIP-Pfad: " + name);
                if (name.EndsWith("/", StringComparison.Ordinal)) continue;
                files++;
                uint crc = 0xffffffffu;
                long count = 0;
                byte[] buffer = new byte[65536];
                using (var content = entry.Open())
                {
                    int length;
                    while ((length = content.Read(buffer, 0, buffer.Length)) != 0)
                    {
                        count += length;
                        for (int i = 0; i < length; i++)
                            crc = (crc >> 8) ^ Table[(int)((crc ^ buffer[i]) & 0xff)];
                    }
                }
                if (count != entry.Length || ~crc != entry.Crc32)
                    throw new InvalidDataException("ZIP-Datei beschaedigt: " + name);
            }
        }
        if (files == 0) throw new InvalidDataException("ZIP ohne Dateien: " + path);
        foreach (var name in required)
            if (!names.Contains(name))
                throw new InvalidDataException("ZIP enthaelt nicht: " + name);
        return files;
    }
}
