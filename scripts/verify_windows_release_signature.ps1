[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [Parameter(Mandatory = $true)]
    [string]$ExpectedThumbprint,
    [switch]$TestTamperDetection
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Bind Authenticode commands to the module shipped with this PowerShell
# engine, even when PSModulePath contains another engine's incompatible copy.
$requiredModules = @(
    'Microsoft.PowerShell.Security',
    'Microsoft.PowerShell.Utility'
)
foreach ($moduleName in $requiredModules) {
    $modulePath = Join-Path $PSHOME ("Modules\$moduleName\$moduleName.psd1")
    if (-not (Test-Path -LiteralPath $modulePath -PathType Leaf)) {
        throw "The built-in $moduleName module was not found."
    }
    Import-Module -Name $modulePath -Force -ErrorAction Stop
}

$selectedPath = [IO.Path]::GetFullPath($Path)
if (-not (Test-Path -LiteralPath $selectedPath -PathType Leaf)) {
    throw "Signed release file was not found: $selectedPath"
}
$normalizedThumbprint = ($ExpectedThumbprint -replace '[^0-9A-Fa-f]', '').ToUpperInvariant()
$signature = Get-AuthenticodeSignature -LiteralPath $selectedPath
if ($null -eq $signature.SignerCertificate) {
    throw 'The release file is not Authenticode-signed.'
}
if ($signature.SignerCertificate.Thumbprint.ToUpperInvariant() -ne $normalizedThumbprint) {
    throw 'The signer certificate thumbprint does not match the expected publisher.'
}
if ($signature.Status -notin @('Valid', 'UnknownError', 'NotTrusted')) {
    throw "Signature verification failed. Status: $($signature.Status); $($signature.StatusMessage)"
}

$hash = (Get-FileHash -LiteralPath $selectedPath -Algorithm SHA256).Hash.ToUpperInvariant()
$hashPath = "$selectedPath.sha256.txt"
if (-not (Test-Path -LiteralPath $hashPath -PathType Leaf)) {
    throw "SHA-256 sidecar was not found: $hashPath"
}
$declaredHash = ((Get-Content -LiteralPath $hashPath -Raw) -split '\s+')[0].ToUpperInvariant()
if ($declaredHash -ne $hash) {
    throw 'The SHA-256 sidecar does not match the signed release file.'
}

$tamperDetected = $null
if ($TestTamperDetection) {
    $tamperedPath = Join-Path ([IO.Path]::GetTempPath()) ("EitaaBridgeTamperTest-" + [guid]::NewGuid().ToString('N') + '.exe')
    try {
        Copy-Item -LiteralPath $selectedPath -Destination $tamperedPath
        [IO.File]::AppendAllText($tamperedPath, 'tamper-test', [Text.Encoding]::ASCII)
        $tamperedSignature = Get-AuthenticodeSignature -LiteralPath $tamperedPath
        $tamperDetected = $tamperedSignature.Status -in @('HashMismatch', 'NotSigned')
        if (-not $tamperDetected) {
            throw "Modified-file signature status was $($tamperedSignature.Status), not an invalidated-signature status."
        }
    }
    finally {
        Remove-Item -LiteralPath $tamperedPath -Force -ErrorAction SilentlyContinue
    }
}

[pscustomobject]@{
    Path = $selectedPath
    Sha256 = $hash
    SignerThumbprint = $signature.SignerCertificate.Thumbprint.ToUpperInvariant()
    SignatureStatus = $signature.Status.ToString()
    Timestamped = $null -ne $signature.TimeStamperCertificate
    TamperDetectionTested = [bool]$TestTamperDetection
    TamperDetected = $tamperDetected
} | ConvertTo-Json -Depth 3
