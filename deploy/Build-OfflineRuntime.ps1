#Requires -Version 7.0
<#
.SYNOPSIS
    Baut auf Windows x64 eine relocatable, offline benutzbare Runtime.
.DESCRIPTION
    Nur waehrend des Windows-CI-Builds herunterladen. SHA-256-pinning
    verhindert den stillen Austausch fremder Binaerdateien. Keine
    Downloads, kein pip und kein installiertes Python auf dem Ziel-PC.
    Lizenz-/Quellcodehinweise im erzeugten runtime/licenses/ beibehalten.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$PackageDir
)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Offline-Runtime kann nur auf Windows x64 gebaut werden' }
$runtime = Join-Path $PackageDir 'runtime'
if (Test-Path $runtime) { throw "Runtime-Ordner bereits vorhanden: $runtime" }
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$temp = Join-Path $env:RUNNER_TEMP 'genesis-offline-runtime-build'
if (Test-Path $temp) { throw "Temporärer Buildordner bereits vorhanden: $temp" }
New-Item -ItemType Directory -Path $temp | Out-Null

function Get-VerifiedArchive {
    param([string]$Url, [string]$Hash, [string]$Name)
    $archive = Join-Path $temp $Name
    Write-Host "Lade $Name (nur auf dem Build-Runner): $Url"
    Invoke-WebRequest -Uri $Url -OutFile $archive -MaximumRedirection 8
    $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Hash) {
        throw "SHA-256-Abweichung fuer $Name! Erwartet $Hash, erhalten $actual"
    }
    return $archive
}

try {
    $pythonArchive = Get-VerifiedArchive `
        -Url 'https://github.com/astral-sh/python-build-standalone/releases/download/20261013/cpython-3.11.17%2B20261013-x86_64-pc-windows-msvc-install_only.tar.gz' `
        -Hash '7616ab1f74aab975bd91eb0a657a74a092a63a46cac38c5f3f9415c79fd781f5' `
        -Name 'python.tar.gz'
    $pyExtract = Join-Path $temp 'python-extract'
    New-Item -ItemType Directory -Path $pyExtract | Out-Null
    & tar -xzf $pythonArchive -C $pyExtract
    if ($LASTEXITCODE -ne 0) { throw 'Portable-Python-Archiv konnte nicht entpackt werden' }
    $pythonExe = Get-ChildItem $pyExtract -Recurse -Filter python.exe -File |
        Where-Object { $_.Directory.Name -eq 'install' } | Select-Object -First 1
    if (-not $pythonExe) { throw 'python.exe fehlt im python-build-standalone-Archiv' }
    $pythonDir = Join-Path $runtime 'python'
    Copy-Item -LiteralPath $pythonExe.Directory.FullName -Destination $pythonDir -Recurse
    $portablePython = Join-Path $pythonDir 'python.exe'
    & $portablePython -c 'import sys; print("Portable Python:", sys.version, sys.prefix)'
    if ($LASTEXITCODE -ne 0) { throw 'Portables Python startet nicht' }

    # Die Paketdatei wurde zuvor von Build-Package.ps1 erzeugt. pip laeuft
    # NUR im Build: alle Wheels landen in der mitgelieferten Python-Runtime.
    $requirements = Join-Path $PackageDir 'backend\requirements.txt'
    & $portablePython -m pip install --disable-pip-version-check -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Offline-Kernabhaengigkeiten konnten nicht in Python installiert werden' }
    # Voice Studio ist optional. Ein fehlendes piper darf die Kernapp
    # nicht blockieren und wird im Buildprotokoll transparent gemeldet.
    & $portablePython -m pip install --disable-pip-version-check `
        -r (Join-Path $PackageDir 'backend\requirements-voice.txt')
    if ($LASTEXITCODE -ne 0) { Write-Warning 'piper-tts nicht im Offline-Paket; Voice Studio bleibt optional' }

    $ffArchive = Get-VerifiedArchive `
        -Url 'https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-10-15-13-03/ffmpeg-n8.1.3-18-g46d899d7a0-win64-lgpl-shared-8.1.zip' `
        -Hash '4acd82323c2cad9c7ffea5b8e335ebcda39beae83a3138d729545e5a7666a3fd' `
        -Name 'ffmpeg.zip'
    $ffExtract = Join-Path $temp 'ffmpeg-extract'
    Expand-Archive -LiteralPath $ffArchive -DestinationPath $ffExtract
    $ffmpegExe = Get-ChildItem $ffExtract -Recurse -Filter ffmpeg.exe -File | Select-Object -First 1
    $ffprobeExe = Get-ChildItem $ffExtract -Recurse -Filter ffprobe.exe -File | Select-Object -First 1
    if (-not $ffmpegExe -or -not $ffprobeExe) { throw 'ffmpeg.exe/ffprobe.exe fehlen' }
    $ffDir = Join-Path $runtime 'tools\ffmpeg'
    New-Item -ItemType Directory -Force -Path $ffDir | Out-Null
    # LGPL-Shared-Build: DLLs muessen mit den EXEs zusammen bleiben.
    Copy-Item -Path (Join-Path $ffmpegExe.Directory.FullName '*') -Destination $ffDir -Recurse -Force

    $fpArchive = Get-VerifiedArchive `
        -Url 'https://github.com/acoustid/chromaprint/releases/download/v1.6.2/chromaprint-fpcalc-1.6.2-windows-x86_64.zip' `
        -Hash 'b74369726676670af3ab0eadff45f960cf969fdf4a87a971ba37eaf8d530e874' `
        -Name 'chromaprint.zip'
    $fpExtract = Join-Path $temp 'chromaprint-extract'
    Expand-Archive -LiteralPath $fpArchive -DestinationPath $fpExtract
    $fpcalcExe = Get-ChildItem $fpExtract -Recurse -Filter fpcalc.exe -File | Select-Object -First 1
    if (-not $fpcalcExe) { throw 'fpcalc.exe fehlt im Chromaprint-Archiv' }
    $fpDir = Join-Path $runtime 'tools\chromaprint'
    New-Item -ItemType Directory -Force -Path $fpDir | Out-Null
    Copy-Item -Path (Join-Path $fpcalcExe.Directory.FullName '*') -Destination $fpDir -Recurse -Force

    # Bei Weitergabe aller drei Projekte muessen die Lizenzinformationen
    # und Bezugsquellen der zugehoerigen Quelltexte auffindbar bleiben.
    $licenses = Join-Path $runtime 'licenses'
    New-Item -ItemType Directory -Force -Path $licenses | Out-Null
    foreach ($item in @(
        @{ Dir = $pythonExe.Directory.FullName; Label = 'python' },
        @{ Dir = (Split-Path $ffmpegExe.Directory.FullName); Label = 'ffmpeg' },
        @{ Dir = $fpcalcExe.Directory.FullName; Label = 'chromaprint' }
    )) {
        Get-ChildItem $item.Dir -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^(LICENSE|COPYING|NOTICE)(\.|$)' -and $_.Length -lt 2000000 } |
            ForEach-Object {
                $name = "$($item.Label)-$($_.Name)"
                Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $licenses $name) -Force
            }
    }
    @"
Python 3.11.17: https://github.com/astral-sh/python-build-standalone/releases/tag/20261013
Python-Quellcode: https://github.com/python/cpython/tree/v3.11.17
FFmpeg LGPL-Build: https://github.com/BtbN/FFmpeg-Builds/releases/tag/autobuild-2026-10-15-13-03
FFmpeg-Quellcode: https://github.com/FFmpeg/FFmpeg
Chromaprint 1.6.2: https://github.com/acoustid/chromaprint/releases/tag/v1.6.2
Chromaprint-Quellcode: https://github.com/acoustid/chromaprint/tree/v1.6.2
Python-Pakete/deren Lizenzen: siehe runtime/python/Lib/site-packages/*.dist-info
"@ | Set-Content (Join-Path $licenses 'SOURCES.txt') -Encoding utf8

    # Ein Windows-Prozess ohne globale ffmpeg-/fpcalc-Installation soll die
    # mitgelieferten Werkzeuge ueber den lokalen PATH finden.
    $env:PATH = "$ffDir;$fpDir;$env:PATH"
    & $portablePython -c 'import fastapi, sqlalchemy, uvicorn'
    if ($LASTEXITCODE -ne 0) { throw 'Portables Python kann Core-Pakete nicht importieren' }
    & (Join-Path $ffDir 'ffmpeg.exe') -version | Select-Object -First 1
    if ($LASTEXITCODE -ne 0) { throw 'ffmpeg.exe nicht lauffaehig' }
    & (Join-Path $ffDir 'ffprobe.exe') -version | Select-Object -First 1
    if ($LASTEXITCODE -ne 0) { throw 'ffprobe.exe nicht lauffaehig' }
    & (Join-Path $fpDir 'fpcalc.exe') -version
    if ($LASTEXITCODE -ne 0) { throw 'fpcalc.exe nicht lauffaehig' }
    Write-Host 'Offline-Runtime und Medienwerkzeuge gebaut und auf Windows gestartet.'
} finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
