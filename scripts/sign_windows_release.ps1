[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Path,
    [Parameter(Mandatory = $true)]
    [string]$Thumbprint,
    [string]$TimestampServer
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Prefer the security module shipped with the current PowerShell engine. A
# caller-provided PSModulePath can otherwise make Windows PowerShell 5.1 try to
# autoload an incompatible PowerShell 7 module with the same name.
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
    throw "Release file was not found: $selectedPath"
}
if ([IO.Path]::GetExtension($selectedPath) -ine '.exe') {
    throw 'Only Windows EXE release files are accepted by this signing path.'
}

$normalizedThumbprint = ($Thumbprint -replace '[^0-9A-Fa-f]', '').ToUpperInvariant()
if ($normalizedThumbprint.Length -ne 40) {
    throw 'Certificate thumbprint must contain exactly 40 hexadecimal characters.'
}
$certificateStore = [Security.Cryptography.X509Certificates.X509Store]::new(
    [Security.Cryptography.X509Certificates.StoreName]::My,
    [Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser
)
$certificateStore.Open(
    [Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly -bor
    [Security.Cryptography.X509Certificates.OpenFlags]::OpenExistingOnly
)
$matches = $certificateStore.Certificates.Find(
    [Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint,
    $normalizedThumbprint,
    $false
)
if ($matches.Count -ne 1) {
    $certificateStore.Close()
    throw "Exactly one signing certificate was required; found $($matches.Count)."
}
$certificate = $matches[0]
if (-not $certificate.HasPrivateKey) {
    throw 'The selected certificate has no private signing key.'
}
$codeSigningOid = '1.3.6.1.5.5.7.3.3'
if (-not ($certificate.EnhancedKeyUsageList.ObjectId -contains $codeSigningOid)) {
    throw 'The selected certificate is not valid for code signing.'
}
if ($certificate.NotBefore -gt (Get-Date) -or $certificate.NotAfter -lt (Get-Date)) {
    $certificateStore.Close()
    throw 'The selected signing certificate is outside its validity period.'
}

$signingParameters = @{
    LiteralPath = $selectedPath
    Certificate = $certificate
    HashAlgorithm = 'SHA256'
    IncludeChain = 'Signer'
    Force = $true
}
if (-not [string]::IsNullOrWhiteSpace($TimestampServer)) {
    $signingParameters.TimestampServer = $TimestampServer
}
$signature = Set-AuthenticodeSignature @signingParameters

$verified = Get-AuthenticodeSignature -LiteralPath $selectedPath
if ($null -eq $verified.SignerCertificate) {
    throw "Authenticode signature was not written. Status: $($verified.Status)"
}
if ($verified.SignerCertificate.Thumbprint.ToUpperInvariant() -ne $normalizedThumbprint) {
    throw 'The release signer thumbprint does not match the requested certificate.'
}
if ($verified.Status -notin @('Valid', 'UnknownError', 'NotTrusted')) {
    throw "Authenticode verification failed. Status: $($verified.Status); $($verified.StatusMessage)"
}
if (-not [string]::IsNullOrWhiteSpace($TimestampServer) -and $null -eq $verified.TimeStamperCertificate) {
    $certificateStore.Close()
    throw 'The timestamp server was requested but the resulting signature has no timestamp.'
}

$hash = (Get-FileHash -LiteralPath $selectedPath -Algorithm SHA256).Hash.ToUpperInvariant()
$hashPath = "$selectedPath.sha256.txt"
$hashLine = "$hash  $([IO.Path]::GetFileName($selectedPath))`r`n"
[IO.File]::WriteAllText($hashPath, $hashLine, [Text.UTF8Encoding]::new($false))
$certificateStore.Close()

[pscustomobject]@{
    Path = $selectedPath
    Sha256 = $hash
    SignerThumbprint = $verified.SignerCertificate.Thumbprint.ToUpperInvariant()
    SignatureStatus = $verified.Status.ToString()
    Timestamped = $null -ne $verified.TimeStamperCertificate
    HashFile = $hashPath
} | ConvertTo-Json -Depth 3
