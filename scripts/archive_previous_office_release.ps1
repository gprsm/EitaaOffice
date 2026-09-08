[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ReleaseDirectory
)

$ErrorActionPreference = 'Stop'

function Get-Sha256Hex {
    param([Parameter(Mandatory = $true)][string]$Path)

    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        return ([BitConverter]::ToString($sha256.ComputeHash($stream))).Replace('-', '')
    }
    finally {
        $stream.Dispose()
        $sha256.Dispose()
    }
}

$releaseRoot = (Resolve-Path -LiteralPath $ReleaseDirectory).Path.TrimEnd('\')
$candidates = @(
    Get-ChildItem -LiteralPath $releaseRoot -File | Where-Object {
        $_.Name -match '^EitaaBridge-.*-((?:Gui)?Setup-x64\.exe|Portable\.zip)(\.sha256\.txt)?$'
    }
)

if ($candidates.Count -eq 0) {
    Write-Output 'No previous Office release artifact was found.'
    exit 0
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$archiveRoot = Join-Path $releaseRoot 'archive'
$destination = Join-Path $archiveRoot $stamp
if (Test-Path -LiteralPath $destination) {
    $destination = Join-Path $archiveRoot ($stamp + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$resolvedDestination = (Resolve-Path -LiteralPath $destination).Path

$manifestEntries = @()
foreach ($candidate in $candidates) {
    if (-not [string]::Equals($candidate.DirectoryName.TrimEnd('\'), $releaseRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to archive an artifact outside the direct release directory."
    }
    $hash = Get-Sha256Hex -Path $candidate.FullName
    $manifestEntries += [ordered]@{
        name = $candidate.Name
        bytes = $candidate.Length
        sha256 = $hash
    }
    Move-Item -LiteralPath $candidate.FullName -Destination (Join-Path $resolvedDestination $candidate.Name)
}

$manifest = [ordered]@{
    format = 'eitaa-bridge-office-release-archive-v1'
    archived_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    source_directory = $releaseRoot
    artifacts = $manifestEntries
}
$manifestPath = Join-Path $resolvedDestination 'ARCHIVE_MANIFEST.json'
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Output $resolvedDestination
