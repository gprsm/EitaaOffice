[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Source,
    [Parameter(Mandatory = $true)]
    [string]$Output,
    [int[]]$Sizes = @(16, 20, 24, 32, 40, 48, 64, 128, 256)
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.Drawing

$sourcePath = [IO.Path]::GetFullPath($Source)
$outputPath = [IO.Path]::GetFullPath($Output)
if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
    throw "Icon source was not found: $sourcePath"
}
if ([IO.Path]::GetExtension($sourcePath) -ine '.png') {
    throw 'The reproducible Windows icon path accepts a PNG source.'
}

$expectedSizes = @(16, 20, 24, 32, 40, 48, 64, 128, 256)
$normalizedSizes = @($Sizes | Sort-Object -Unique)
if (($normalizedSizes -join ',') -ne ($expectedSizes -join ',')) {
    throw 'Windows icon sizes must be exactly 16, 20, 24, 32, 40, 48, 64, 128 and 256.'
}

$sourceImage = [Drawing.Bitmap]::new($sourcePath)
try {
    if ($sourceImage.Width -ne $sourceImage.Height -or $sourceImage.Width -lt 256) {
        throw 'Icon source must be square and at least 256 by 256 pixels.'
    }
    if (-not [Drawing.Image]::IsAlphaPixelFormat($sourceImage.PixelFormat)) {
        throw 'Icon source must contain an alpha channel.'
    }

    $frames = [Collections.Generic.List[byte[]]]::new()
    foreach ($size in $normalizedSizes) {
        $bitmap = [Drawing.Bitmap]::new(
            $size,
            $size,
            [Drawing.Imaging.PixelFormat]::Format32bppArgb
        )
        try {
            $graphics = [Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.CompositingMode = [Drawing.Drawing2D.CompositingMode]::SourceCopy
                $graphics.CompositingQuality = [Drawing.Drawing2D.CompositingQuality]::HighQuality
                $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::HighQuality
                $graphics.PixelOffsetMode = [Drawing.Drawing2D.PixelOffsetMode]::HighQuality
                $graphics.Clear([Drawing.Color]::Transparent)
                $graphics.DrawImage(
                    $sourceImage,
                    [Drawing.Rectangle]::new(0, 0, $size, $size),
                    0,
                    0,
                    $sourceImage.Width,
                    $sourceImage.Height,
                    [Drawing.GraphicsUnit]::Pixel
                )
            }
            finally {
                $graphics.Dispose()
            }
            $stream = [IO.MemoryStream]::new()
            try {
                $bitmap.Save($stream, [Drawing.Imaging.ImageFormat]::Png)
                $frames.Add($stream.ToArray())
            }
            finally {
                $stream.Dispose()
            }
        }
        finally {
            $bitmap.Dispose()
        }
    }

    $outputDirectory = Split-Path -Parent $outputPath
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
    $temporaryPath = Join-Path $outputDirectory ('.' + [IO.Path]::GetFileName($outputPath) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $fileStream = [IO.File]::Open(
            $temporaryPath,
            [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None
        )
        $writer = [IO.BinaryWriter]::new($fileStream)
        try {
            $writer.Write([uint16]0)
            $writer.Write([uint16]1)
            $writer.Write([uint16]$normalizedSizes.Count)
            $frameOffset = 6 + (16 * $normalizedSizes.Count)
            for ($index = 0; $index -lt $normalizedSizes.Count; $index++) {
                $size = $normalizedSizes[$index]
                $frame = $frames[$index]
                $writer.Write([byte]$(if ($size -eq 256) { 0 } else { $size }))
                $writer.Write([byte]$(if ($size -eq 256) { 0 } else { $size }))
                $writer.Write([byte]0)
                $writer.Write([byte]0)
                $writer.Write([uint16]1)
                $writer.Write([uint16]32)
                $writer.Write([uint32]$frame.Length)
                $writer.Write([uint32]$frameOffset)
                $frameOffset += $frame.Length
            }
            foreach ($frame in $frames) {
                $writer.Write($frame)
            }
            $writer.Flush()
            $fileStream.Flush($true)
        }
        finally {
            $writer.Dispose()
            $fileStream.Dispose()
        }
        Move-Item -LiteralPath $temporaryPath -Destination $outputPath -Force
    }
    finally {
        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
    }
}
finally {
    $sourceImage.Dispose()
}

[pscustomobject]@{
    Source = $sourcePath
    SourceSha256 = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToUpperInvariant()
    Output = $outputPath
    OutputSha256 = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToUpperInvariant()
    Sizes = $normalizedSizes
} | ConvertTo-Json -Depth 3
