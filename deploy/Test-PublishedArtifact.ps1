#Requires -Version 7.0
<#
.SYNOPSIS
    Laedt das GitHub-Artefakt auf einem ZWEITEN Windows-Runner herunter und
    verifiziert die aeussere ZIP und ihre Inhalte nach dem Upload.
.DESCRIPTION
    Nur fuer GitHub Actions: GITHUB_TOKEN kommt aus github.token in der
    Job-Umgebung. Nutzt RUNNER_TEMP, niemals den 100-MiB-Entwicklungs-
    Workspace oder den Rechner des Nutzers. Keine geheimen Header ausgeben.
#>
[CmdletBinding()]
param([Parameter(Mandatory)][string]$ArtifactId)
$ErrorActionPreference = 'Stop'
if ($ArtifactId -notmatch '^[1-9][0-9]*$' -or
    -not $env:GITHUB_TOKEN -or -not $env:GITHUB_REPOSITORY -or
    -not $env:GITHUB_RUN_ID -or -not $env:GITHUB_SHA -or -not $env:RUNNER_TEMP) {
    throw 'GitHub-Actions-Artefakt-ID/Runner-Umgebung unvollstaendig'
}
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$commit = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $commit -cne $env:GITHUB_SHA) {
    throw 'Checkout und GitHub-Lauf verwenden verschiedene Commits'
}
$headers = @{
    Authorization = "Bearer $env:GITHUB_TOKEN"
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
}
$endpoint = "https://api.github.com/repos/$env:GITHUB_REPOSITORY/actions/artifacts/$ArtifactId"
$metadata = Invoke-RestMethod -Uri $endpoint -Headers $headers -ErrorAction Stop
if ($metadata.expired -or $metadata.name -ne 'GenesisMediaManager-Komplettpaket-zip' -or
    $metadata.id -ne [long]$ArtifactId -or
    $metadata.workflow_run.id -ne [long]$env:GITHUB_RUN_ID -or
    $metadata.workflow_run.head_sha -cne $commit -or
    $metadata.digest -cnotmatch '^sha256:([0-9a-f]{64})$') {
    throw 'Artefakt-Metadaten passen nicht zu diesem Commit und CI-Lauf'
}
$expectedHash = ([string]$metadata.digest).Substring(7)
$temp = Join-Path $env:RUNNER_TEMP "genesis-verify-$env:GITHUB_RUN_ID"
if (Test-Path -LiteralPath $temp) { throw "Runner-Temp-Ordner belegt: $temp" }
New-Item -ItemType Directory -Path $temp -ErrorAction Stop | Out-Null
try {
    $outerZip = Join-Path $temp 'GenesisMediaManager-Komplettpaket-zip.zip'
    $extracted = Join-Path $temp 'extracted'
    # API-Download liefert eine zeitlich begrenzte Redirect-URL. Token wird
    # nur im HTTP-Header gesendet und niemals im Log oder Paket gespeichert.
    Invoke-WebRequest -Uri "$endpoint/zip" -Headers $headers -MaximumRedirection 10 `
        -OutFile $outerZip -ErrorAction Stop
    if ((Get-Item -LiteralPath $outerZip).Length -ne [long]$metadata.size_in_bytes) {
        throw 'Heruntergeladenes Artefakt hat nicht die GitHub-Metadatengroesse'
    }
    $hash = (Get-FileHash -LiteralPath $outerZip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -cne $expectedHash) { throw 'SHA-256 des heruntergeladenen aeusseren ZIP weicht vom GitHub-Digest ab' }
    Write-Host "::notice::GitHub-Artefakt $ArtifactId unabhaengig geladen; SHA-256/Laenge des aeusseren ZIP stimmen"

    # ZUERST alle aeusseren Eintraege dekomprimieren und CRC/Laenge
    # pruefen, erst dann die vertrauenswuerdigeren Namen extrahieren.
    if (-not ('BundleZipIntegrity' -as [type])) {
        Add-Type -Path (Join-Path $PSScriptRoot 'BundleZipIntegrity.cs')
    }
    $names = @(
        'GenesisMediaManager-Inno-Setup.exe','GenesisMediaManager-Setup.msi',
        'GenesisMediaManager-Setup.zip','GenesisMediaManager.iss',
        'GenesisMediaManager-Quellcode.zip','README-INSTALL.md',
        'INSTALLER_AUDIT.md','LIESMICH-ZUERST.txt','BUILDINFO.txt','SHA256SUMS.txt'
    )
    $count = [BundleZipIntegrity]::Check($outerZip, $names)
    if ($count -ne $names.Count) { throw "Aeussere ZIP hat $count statt $($names.Count) Dateien" }
    Write-Host "Aeussere ZIP vollstaendig dekomprimiert, $count Dateien samt CRC32 OK"
    Expand-Archive -LiteralPath $outerZip -DestinationPath $extracted -ErrorAction Stop
    & (Join-Path $PSScriptRoot 'Test-DownloadBundle.ps1') -BundleDir $extracted
    Write-Host "::notice::Nach Upload: aeusseres ZIP und entpacktes Paket samt neun SHA-256-Dateien und inneren ZIPs bestanden"
} finally {
    # Nur den in DIESEM Schritt eigens erzeugten Runner-Temp-Ordner entfernen.
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
