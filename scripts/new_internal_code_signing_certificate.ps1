[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,
    [string]$Subject = 'CN=Eitaa Bridge Internal Publisher',
    [ValidateRange(1, 10)]
    [int]$ValidityYears = 5,
    [switch]$ForceNew
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$codeSigningOid = '1.3.6.1.5.5.7.3.3'
$storeLocation = 'Cert:\CurrentUser\My'
$resolvedOutput = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

$certificate = $null
if (-not $ForceNew) {
    $certificate = Get-ChildItem -Path $storeLocation |
        Where-Object {
            $_.Subject -eq $Subject -and
            $_.HasPrivateKey -and
            $_.NotAfter -gt (Get-Date).AddMonths(6) -and
            ($_.EnhancedKeyUsageList.ObjectId -contains $codeSigningOid)
        } |
        Sort-Object NotAfter -Descending |
        Select-Object -First 1
}

if ($null -eq $certificate) {
    $certificate = New-SelfSignedCertificate `
        -Type Custom `
        -Subject $Subject `
        -FriendlyName 'Eitaa Bridge Internal Code Signing' `
        -CertStoreLocation $storeLocation `
        -KeyAlgorithm RSA `
        -KeyLength 3072 `
        -HashAlgorithm SHA256 `
        -KeySpec Signature `
        -KeyUsage DigitalSignature `
        -KeyExportPolicy NonExportable `
        -NotAfter (Get-Date).AddYears($ValidityYears) `
        -TextExtension @(
            "2.5.29.37={text}$codeSigningOid",
            '2.5.29.19={critical}{text}ca=false'
        )
}

if (-not $certificate.HasPrivateKey) {
    throw 'The selected certificate has no signing key.'
}
if (-not ($certificate.EnhancedKeyUsageList.ObjectId -contains $codeSigningOid)) {
    throw 'The selected certificate is not valid for code signing.'
}

$cerPath = Join-Path $resolvedOutput 'EitaaBridge-Internal-Publisher.cer'
Export-Certificate -Cert $certificate -FilePath $cerPath -Type CERT -Force | Out-Null
$publicCertificate = [Security.Cryptography.X509Certificates.X509Certificate2]::new($cerPath)
if ($publicCertificate.HasPrivateKey) {
    throw 'The exported public CER unexpectedly contains a private key.'
}
if ($publicCertificate.Thumbprint -ne $certificate.Thumbprint) {
    throw 'The exported public certificate thumbprint does not match the signing certificate.'
}

$thumbprint = $certificate.Thumbprint.ToUpperInvariant()
$certificateHash = (Get-FileHash -LiteralPath $cerPath -Algorithm SHA256).Hash.ToUpperInvariant()
$metadata = [ordered]@{
    schema_version = 1
    publisher = 'Eitaa Bridge Internal Publisher'
    subject = $certificate.Subject
    thumbprint_sha1 = $thumbprint
    public_cer_sha256 = $certificateHash
    serial_number = $certificate.SerialNumber
    not_before_utc = $certificate.NotBefore.ToUniversalTime().ToString('o')
    not_after_utc = $certificate.NotAfter.ToUniversalTime().ToString('o')
    signature_hash_algorithm = $certificate.SignatureAlgorithm.FriendlyName
    public_key_algorithm = $certificate.PublicKey.Oid.FriendlyName
    public_key_bits = 3072
    enhanced_key_usage_oid = $codeSigningOid
    private_key_store = $storeLocation
    private_key_export_policy = 'NonExportable'
    private_key_exported = $false
}
$metadataPath = Join-Path $resolvedOutput 'certificate-metadata.json'
$utf8WithBom = [Text.UTF8Encoding]::new($true)
[IO.File]::WriteAllText(
    $metadataPath,
    ($metadata | ConvertTo-Json -Depth 4),
    $utf8WithBom
)

$trustTemplate = @'
[CmdletBinding()]
param([switch]$LocalMachine)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$expectedThumbprint = '__THUMBPRINT__'
$certificatePath = Join-Path $PSScriptRoot 'EitaaBridge-Internal-Publisher.cer'
if (-not (Test-Path -LiteralPath $certificatePath -PathType Leaf)) {
    throw "Public certificate was not found: $certificatePath"
}
$certificate = [Security.Cryptography.X509Certificates.X509Certificate2]::new($certificatePath)
$actualThumbprint = $certificate.Thumbprint.ToUpperInvariant()
if ($actualThumbprint -ne $expectedThumbprint) {
    throw "Certificate thumbprint mismatch. Expected $expectedThumbprint but found $actualThumbprint."
}
if ($certificate.HasPrivateKey) {
    throw 'A public trust bundle must never contain a private key.'
}

$scope = if ($LocalMachine) { 'LocalMachine' } else { 'CurrentUser' }
if ($LocalMachine) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Run PowerShell as Administrator when using -LocalMachine.'
    }
}

Import-Certificate -FilePath $certificatePath -CertStoreLocation "Cert:\$scope\Root" | Out-Null
Import-Certificate -FilePath $certificatePath -CertStoreLocation "Cert:\$scope\TrustedPublisher" | Out-Null

$root = Get-Item -LiteralPath "Cert:\$scope\Root\$expectedThumbprint" -ErrorAction Stop
$publisher = Get-Item -LiteralPath "Cert:\$scope\TrustedPublisher\$expectedThumbprint" -ErrorAction Stop
if ($root.Thumbprint -ne $expectedThumbprint -or $publisher.Thumbprint -ne $expectedThumbprint) {
    throw 'Publisher trust verification failed.'
}
Write-Host "Eitaa Bridge publisher trust installed for $scope."
Write-Host "Thumbprint: $expectedThumbprint"
'@
$trustScriptPath = Join-Path $resolvedOutput 'Install-EitaaBridgeInternalPublisherTrust.ps1'
$trustScript = $trustTemplate.Replace('__THUMBPRINT__', $thumbprint)
[IO.File]::WriteAllText($trustScriptPath, $trustScript, $utf8WithBom)

$guideTemplate = @'
# راهنمای اعتماد به امضای داخلی Eitaa Bridge

این بسته فقط **گواهی عمومی** ناشر را در خود دارد. کلید خصوصی امضا در مخزن شخصی گواهی ویندوزِ رایانه سازنده (`Cert:\CurrentUser\My`) و با سیاست `NonExportable` نگهداری می‌شود و داخل پروژه یا بسته نصب قرار ندارد.

## کنترل هویت گواهی

- ناشر: Eitaa Bridge Internal Publisher
- Thumbprint (SHA-1 شناسه گواهی): `__THUMBPRINT__`
- SHA-256 فایل CER: `__CER_SHA256__`
- پایان اعتبار: `__NOT_AFTER__`

پیش از نصب اعتماد، Thumbprint بالا را از یک مسیر مستقل با سازنده نرم‌افزار تطبیق دهید. اگر حتی یک نویسه متفاوت بود، هیچ فایلی را اجرا نکنید.

## نصب برای کاربر فعلی (پیشنهادی)

1. چهار فایل این پوشه را کنار هم نگه دارید.
2. روی Start کلیک کنید، PowerShell را باز کنید و به این پوشه بروید.
3. دستور زیر را اجرا کنید:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-EitaaBridgeInternalPublisherTrust.ps1
```

این کار گواهی را فقط برای کاربر فعلی در دو مخزن `Root` و `TrustedPublisher` نصب می‌کند.

## نصب برای همه کاربران رایانه

PowerShell را با گزینه Run as administrator باز کنید و اجرا کنید:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-EitaaBridgeInternalPublisherTrust.ps1 -LocalMachine
```

## کنترل امضای Setup

روی فایل Setup راست‌کلیک کنید، Properties را بزنید و در زبانه Digital Signatures نام `Eitaa Bridge Internal Publisher` را ببینید. سپس Details را باز کنید و Thumbprint گواهی امضاکننده را با مقدار بالا تطبیق دهید.

> گواهی Self-signed اعتبار تجاری عمومی ایجاد نمی‌کند. فقط رایانه‌هایی که این CER را آگاهانه اعتماد داده‌اند، ناشر را معتبر می‌شناسند.
'@
$guide = $guideTemplate.Replace('__THUMBPRINT__', $thumbprint)
$guide = $guide.Replace('__CER_SHA256__', $certificateHash)
$guide = $guide.Replace(
    '__NOT_AFTER__',
    $certificate.NotAfter.ToString('yyyy-MM-dd HH:mm:ss zzz')
)
$guidePath = Join-Path $resolvedOutput 'README_TRUST_CERTIFICATE_FA.md'
[IO.File]::WriteAllText($guidePath, $guide, $utf8WithBom)

$thumbprintPath = Join-Path $resolvedOutput 'SIGNING_CERTIFICATE_THUMBPRINT.txt'
[IO.File]::WriteAllText($thumbprintPath, "$thumbprint`r`n", $utf8WithBom)

[pscustomobject]@{
    Thumbprint = $thumbprint
    CertificateStore = "$storeLocation\$thumbprint"
    PublicCertificate = $cerPath
    Metadata = $metadataPath
    TrustInstaller = $trustScriptPath
    PersianGuide = $guidePath
    ReusedExistingCertificate = -not $ForceNew -and $certificate.NotBefore -lt (Get-Date).AddMinutes(-1)
} | ConvertTo-Json -Depth 3
