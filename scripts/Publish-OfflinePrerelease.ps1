#Requires -Version 7.0
<#
.SYNOPSIS
    Veröffentlicht ein bereits getestetes Windows-CI-Artefakt als
    ausdrücklich NICHT vollständig freigegebenes öffentliches Vorab-Release.
.DESCRIPTION
    GitHub Actions Windows-Runner, nie lokaler 100-MiB-Workspace. Lädt nur
    die genau gepinnte Artefakt-ID, vergleicht Run/Commit/Digest, prüft das
    ZIP und testet danach den Release-Link OHNE Authentifizierung erneut.
    GH_TOKEN stammt aus github.token; keine privaten Tokens in Dateien/Logs.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ArtifactId,
    [Parameter(Mandatory)][string]$RunId,
    [Parameter(Mandatory)][string]$TestedCommit,
    [Parameter(Mandatory)][string]$ExpectedDigest,
    [Parameter(Mandatory)][string]$Tag
)
$ErrorActionPreference = 'Stop'
if (-not $env:GH_TOKEN -or -not $env:GITHUB_REPOSITORY -or -not $env:RUNNER_TEMP -or
    $ArtifactId -notmatch '^[1-9][0-9]*$' -or $RunId -notmatch '^[1-9][0-9]*$' -or
    $TestedCommit -cnotmatch '^[0-9a-f]{40}$' -or
    $ExpectedDigest -cnotmatch '^sha256:[0-9a-f]{64}$' -or
    $Tag -cnotmatch '^[A-Za-z0-9._-]+$') {
    throw 'Vorab-Release: ungueltige ID/Pruefsumme/Runner-Umgebung'
}
$repo = $env:GITHUB_REPOSITORY
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$notes = Join-Path $root 'docs\PRERELEASE_NOTES_2026-10-20.md'
$headers = @{
    Authorization = "Bearer $env:GH_TOKEN"
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
}
$endpoint = "https://api.github.com/repos/$repo/actions/artifacts/$ArtifactId"
$artifact = Invoke-RestMethod -Uri $endpoint -Headers $headers -ErrorAction Stop
if ($artifact.expired -or $artifact.name -ne 'GenesisMediaManager-Komplettpaket-zip' -or
    $artifact.id -ne [long]$ArtifactId -or
    $artifact.workflow_run.id -ne [long]$RunId -or
    $artifact.workflow_run.head_sha -cne $TestedCommit -or
    $artifact.digest -cne $ExpectedDigest) {
    throw 'Artefakt stimmt nicht mit dem autorisierten, getesteten Paket ueberein'
}
$existing = & git -C $root ls-remote origin "refs/tags/$Tag"
if ($LASTEXITCODE -ne 0 -or $existing) { throw "Release-Tag existiert oder konnte nicht geprueft werden: $Tag" }
$releaseEndpoint = "https://api.github.com/repos/$repo/releases/tags/$Tag"
# A release with no tag is not expected; avoid overwriting other releases.
try {
    $previous = Invoke-RestMethod -Uri $releaseEndpoint -Headers $headers -ErrorAction Stop
    if ($previous) { throw "Release-Tag bereits vergeben: $Tag" }
} catch {
    if ($_.Exception.Response.StatusCode -ne [System.Net.HttpStatusCode]::NotFound) { throw }
}
$temp = Join-Path $env:RUNNER_TEMP "genesis-public-preview-$ArtifactId"
if (Test-Path -LiteralPath $temp) { throw "Runner-Temp-Ordner schon vorhanden: $temp" }
New-Item -ItemType Directory -Path $temp -ErrorAction Stop | Out-Null
try {
    $zip = Join-Path $temp 'GenesisMediaManager-Komplettpaket.zip'
    Invoke-WebRequest -Uri "$endpoint/zip" -Headers $headers -MaximumRedirection 10 `
        -OutFile $zip -ErrorAction Stop
    if ((Get-Item -LiteralPath $zip).Length -ne [long]$artifact.size_in_bytes -or
        (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ExpectedDigest.Substring(7)) {
        throw 'CI-Artefakt vor Veroeffentlichung: Bytegroesse/SHA-256 falsch'
    }
    Add-Type -Path (Join-Path $root 'deploy\BundleZipIntegrity.cs')
    $names = @(
        'GenesisMediaManager-Inno-Setup.exe','GenesisMediaManager-Setup.msi',
        'GenesisMediaManager-Setup.zip','GenesisMediaManager.iss',
        'GenesisMediaManager-Quellcode.zip','README-INSTALL.md',
        'INSTALLER_AUDIT.md','LIESMICH-ZUERST.txt','BUILDINFO.txt','SHA256SUMS.txt'
    )
    $count = [BundleZipIntegrity]::Check($zip, $names)
    if ($count -ne $names.Count) { throw "ZIP hat $count statt $($names.Count) Dateien" }
    Write-Host '::notice::CI-Artefakt vor Vorab-Release identisch, ZIP-CRC aller Nutzdateien OK'

    $asset = "$zip#GenesisMediaManager-Komplettpaket.zip"
    & gh release create $Tag $asset --repo $repo --target $TestedCommit --prerelease `
        --title 'GENESIS Media Manager 0.2.0 - Windows Offline VORAB (NOT_READY)' `
        --notes-file $notes
    if ($LASTEXITCODE -ne 0) { throw 'GitHub-Vorab-Release konnte nicht erstellt/hochgeladen werden' }

    $release = Invoke-RestMethod -Uri $releaseEndpoint -Headers $headers -ErrorAction Stop
    $matching = @($release.assets | Where-Object { $_.name -ceq 'GenesisMediaManager-Komplettpaket.zip' })
    if ($release.draft -or -not $release.prerelease -or
        $release.tag_name -cne $Tag -or $matching.Count -ne 1 -or
        $matching[0].size -ne [long]$artifact.size_in_bytes -or
        $matching[0].state -ne 'uploaded') {
        throw 'Vorab-Release/Asset nicht korrekt publiziert'
    }
    $tagLines = @(& git -C $root ls-remote origin "refs/tags/$Tag" "refs/tags/$Tag^{}")
    if ($LASTEXITCODE -ne 0 -or $tagLines.Count -eq 0) {
        throw 'Release-Tag konnte nicht erneut abgefragt werden'
    }
    # Bei annotierten Tags zeigt ^{} auf den Commit; bei leichten Tags
    # bereits der normale Ref. Nicht nur die Tag-Objekt-ID vergleichen.
    $peeled = @($tagLines | Where-Object { $_ -match '\^\{\}$' })
    $tagRef = if ($peeled.Count -gt 0) { ($peeled[0] -split '\s+')[0] }
        else { ($tagLines[0] -split '\s+')[0] }
    if ($tagRef -cne $TestedCommit) {
        throw 'Release-Tag zeigt nicht auf den getesteten Commit'
    }
    $publicUrl = "https://github.com/$repo/releases/download/$Tag/GenesisMediaManager-Komplettpaket.zip"
    $anonymous = Join-Path $temp 'anonym-heruntergeladen.zip'
    # Absichtlich KEIN Authorization-Header/WebSession: Benutzer ohne
    # Anmeldung muessen genau diesen Link ebenfalls herunterladen koennen.
    Invoke-WebRequest -Uri $publicUrl -MaximumRedirection 10 -OutFile $anonymous -ErrorAction Stop
    $downloadHash = (Get-FileHash -LiteralPath $anonymous -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-Item -LiteralPath $anonymous).Length -ne [long]$artifact.size_in_bytes -or
        $downloadHash -cne $ExpectedDigest.Substring(7)) {
        throw 'Oeffentlicher Release-Link lieferte nicht die getestete ZIP'
    }
    Write-Host "::notice::Anonymer Release-Download und SHA-256 bestanden: $publicUrl"
} finally {
    # Nur den selbst erzeugten Windows-CI-Tempordner entfernen.
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
}
