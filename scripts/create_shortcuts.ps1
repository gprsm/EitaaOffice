param([string]$Root = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $Root 'EitaaBridge.bat'
if (-not (Test-Path $launcher)) { throw "Launcher was not found: $launcher" }
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
  $shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,14"
  $shortcut.Description = 'Eitaa Bridge Desktop'
  $shortcut.Save()
}
Write-Output 'Desktop and Start Menu shortcuts created.'
