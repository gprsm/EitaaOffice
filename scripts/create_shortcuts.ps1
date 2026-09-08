param([string]$Root = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $Root 'EitaaBridge.bat'
if (-not (Test-Path $launcher)) { throw "Launcher was not found: $launcher" }
$icon = Join-Path $Root 'assets\EitaaBridge.ico'
if (-not (Test-Path $icon)) { throw "Application icon was not found: $icon" }
$shell = New-Object -ComObject WScript.Shell
$targets = @(
  (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Eitaa Bridge.lnk'),
  (Join-Path ([Environment]::GetFolderPath('Programs')) 'Eitaa Bridge\Eitaa Bridge.lnk')
)
foreach ($target in $targets) {
  $directory = Split-Path -Parent $target
  New-Item -ItemType Directory -Force -Path $directory | Out-Null
  $shortcut = $shell.CreateShortcut($target)
  $shortcut.TargetPath = $launcher
  $shortcut.WorkingDirectory = $Root
  $shortcut.IconLocation = "$icon,0"
  $shortcut.Description = 'Eitaa Bridge Desktop'
  $shortcut.Save()
}
Write-Output 'Desktop and Start Menu shortcuts created.'
