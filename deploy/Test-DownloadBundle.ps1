#Requires -Version 7.0
<#
.SYNOPSIS
    Prueft den fertigen Downloadordner vor dem GitHub-Artefakt-Upload.
.DESCRIPTION
    Exakte Nutzdateiliste, unabhängiger SHA-256-Abgleich und vollstaendige
    ZIP-Dekompression mit CRC32 jeder Datei. Keine grosse Kopie/Extraktion
    im Entwicklungs-Workspace. Das aeussere, von GitHub NACH diesem Schritt
    erzeugte Artefakt-ZIP kann hier noch nicht geprueft werden.
#>
[CmdletBinding()]
param([Parameter(Mandatory)][string]$BundleDir)
$ErrorActionPreference = 'Stop'
$bundle = (Resolve-Path -LiteralPath $BundleDir -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath $bundle -PathType Container)) {
    throw "Downloadordner fehlt: $BundleDir"
}

$expected = @(
    'GenesisMediaManager-Inno-Setup.exe',
    'GenesisMediaManager-Setup.msi',
    'GenesisMediaManager-Setup.zip',
    'GenesisMediaManager.iss',
    'GenesisMediaManager-Quellcode.zip',
    'README-INSTALL.md',
    'INSTALLER_AUDIT.md',
    'LIESMICH-ZUERST.txt',
    'BUILDINFO.txt'
)
$actual = @(Get-ChildItem -LiteralPath $bundle -Force)
$allowed = @($expected) + @('SHA256SUMS.txt')
$unexpected = @($actual | Where-Object {
    -not $_.PSIsContainer -and $_.Name -cnotin $allowed -or $_.PSIsContainer -or
    (($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
})
if ($actual.Count -ne $allowed.Count -or $unexpected.Count -gt 0) {
    throw "Downloadordner: $($actual.Count) Eintraege statt $($allowed.Count), unerwartet: $($unexpected.Name -join ', ')"
}
foreach ($name in $allowed) {
    $file = Join-Path $bundle $name
    if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or
        (Get-Item -LiteralPath $file).Length -eq 0) {
        throw "Leere oder fehlende Download-Datei: $name"
    }
}
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$commit = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or
    -not (Select-String -LiteralPath (Join-Path $bundle 'BUILDINFO.txt') -SimpleMatch -Pattern "Commit: $commit" -Quiet)) {
    throw "BUILDINFO.txt nennt nicht den aktuellen Commit $commit"
}

$manifest = Get-Content -LiteralPath (Join-Path $bundle 'SHA256SUMS.txt') -Encoding utf8
if ($manifest.Count -ne $expected.Count) {
    throw "SHA256SUMS.txt: $($manifest.Count) statt $($expected.Count) Hash-Zeilen"
}
$hashedNames = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($line in $manifest) {
    if ($line -cnotmatch '^([0-9a-f]{64})  ([^/\\\r\n]+)$') {
        throw "Ungueltige SHA256SUMS.txt-Zeile: $line"
    }
    $digest = $Matches[1]
    $name = $Matches[2]
    if ($name -cnotin $expected -or -not $hashedNames.Add($name)) {
        throw "Fremder/doppelter Dateiname in SHA256SUMS.txt: $name"
    }
    $actualHash = (Get-FileHash -LiteralPath (Join-Path $bundle $name) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -cne $digest) { throw "SHA-256 weicht ab: $name" }
    Write-Host "SHA-256 OK: $name"
}
if ($hashedNames.Count -ne $expected.Count) { throw 'Nicht alle Nutzdateien gehasht' }

# ZipArchive listet nicht bloss die zentrale Dateitabelle: Jede ZIP-Datei
# wird bis zum Ende gelesen und das unabhaengig berechnete CRC32 mit dem
# gespeicherten Eintrag verglichen. Festen Puffer statt GB-RAM/Extraktion.
if (-not ('BundleZipIntegrity' -as [type])) {
    Add-Type -Path (Join-Path $PSScriptRoot 'BundleZipIntegrity.cs')
}
$packageZip = Join-Path $bundle 'GenesisMediaManager-Setup.zip'
$sourceZip = Join-Path $bundle 'GenesisMediaManager-Quellcode.zip'
$packageCount = [BundleZipIntegrity]::Check($packageZip, @(
    'client/GenesisMediaManager.exe', 'backend/run_api.py', 'start.bat',
    'runtime/python/python.exe', 'runtime/tools/ffmpeg/ffmpeg.exe',
    'runtime/tools/ffmpeg/ffprobe.exe', 'runtime/tools/chromaprint/fpcalc.exe'))
Write-Host "Paket-ZIP vollstaendig dekomprimiert, $packageCount Dateien samt CRC32 OK"
$sourceCount = [BundleZipIntegrity]::Check($sourceZip, @(
    'README.md', 'PROGRESS.md', 'deploy/inno/GenesisMediaManager.iss',
    'deploy/README-INSTALL.md'))
Write-Host "Quellcode-ZIP vollstaendig dekomprimiert, $sourceCount Dateien samt CRC32 OK"
Write-Host "::notice::Downloadpaket vor Upload geprueft: $($expected.Count) SHA-256-Dateien, beide inneren ZIPs vollständig dekomprimiert/CRC32-geprueft"
