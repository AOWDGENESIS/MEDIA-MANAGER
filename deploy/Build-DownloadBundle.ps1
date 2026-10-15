#Requires -Version 7.0
<#
.SYNOPSIS
    Stellt nach erfolgreichem Windows-Build ein einziges Download-Artefakt
    mit allen drei Installationsvarianten, .iss und Quellcode zusammen.
.DESCRIPTION
    Nur auf dem Windows-CI-Runner ausfuehren: die gebauten Binaerdateien
    sind zusammen deutlich groesser als die 100-MB-Workspace-Grenze.
    actions/upload-artifact packt den erzeugten ORDNER in eine ZIP-Datei;
    nicht hier nochmals ein zusaetzliches aeusseres ZIP erstellen.
#>
[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path $env:RUNNER_TEMP 'GenesisMediaManager-Komplettpaket')
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $OutputDir -or (Test-Path $OutputDir)) {
    throw "Downloadordner muss neu und ausserhalb des Repos sein: $OutputDir"
}
New-Item -ItemType Directory -Path $OutputDir -ErrorAction Stop | Out-Null

$contents = @(
    @{ Source = 'build/GenesisMediaManager-Inno-Setup.exe'; Name = 'GenesisMediaManager-Inno-Setup.exe' }
    @{ Source = 'build/package/GenesisMediaManager-Setup.msi'; Name = 'GenesisMediaManager-Setup.msi' }
    @{ Source = 'build/GenesisMediaManager-Setup.zip'; Name = 'GenesisMediaManager-Setup.zip' }
    @{ Source = 'deploy/inno/GenesisMediaManager.iss'; Name = 'GenesisMediaManager.iss' }
    @{ Source = 'deploy/README-INSTALL.md'; Name = 'README-INSTALL.md' }
    @{ Source = 'docs/INSTALLER_AUDIT_2026-10-13.md'; Name = 'INSTALLER_AUDIT.md' }
    @{ Source = 'deploy/bundle/LIESMICH-ZUERST.txt'; Name = 'LIESMICH-ZUERST.txt' }
)
foreach ($item in $contents) {
    $source = Join-Path $repoRoot $item.Source
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Downloadpaket unvollstaendig: $source"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $OutputDir $item.Name) -ErrorAction Stop
}

$sourceArchive = Join-Path $OutputDir 'GenesisMediaManager-Quellcode.zip'
& git -C $repoRoot archive --format=zip -o $sourceArchive HEAD
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $sourceArchive)) {
    throw 'Quellcode-ZIP konnte nicht aus dem aktuellen Arbeitsbranch erzeugt werden'
}
$commit = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Build-Commit konnte nicht ermittelt werden' }
$runUrl = if ($env:GITHUB_RUN_ID -and $env:GITHUB_REPOSITORY) {
    "https://github.com/$env:GITHUB_REPOSITORY/actions/runs/$env:GITHUB_RUN_ID"
} else { 'Lokaler Windows-Build (ohne GitHub-Actions-Link)' }
@(
    'GENESIS Media Manager - Downloadpaket',
    "Commit: $commit",
    "Build: $runUrl",
    'Hinweis: Die Installationsoptionen sind Alternativen, nicht gleichzeitig installieren.'
) | Set-Content -Path (Join-Path $OutputDir 'BUILDINFO.txt') -Encoding utf8

$files = @(Get-ChildItem -LiteralPath $OutputDir -File | Sort-Object Name)
if ($files.Count -ne ($contents.Count + 2)) {
    throw "Downloadpaket enthaelt $($files.Count) statt $($contents.Count + 2) Dateien"
}
$checksums = foreach ($file in $files) {
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $($file.Name)"
}
$checksums | Set-Content -Path (Join-Path $OutputDir 'SHA256SUMS.txt') -Encoding utf8
Write-Host "Downloadpaket bereit: $OutputDir ($($files.Count) Nutzdateien plus SHA256SUMS.txt)"
$files | Select-Object Name, Length | Format-Table -AutoSize
