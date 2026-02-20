param(
  [switch]$OneFile,
  [switch]$Clean
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

Write-Host "[1/4] Install project..."
python -m pip install -e .

Write-Host "[2/4] Install PyInstaller..."
python -m pip install pyinstaller

$distName = "epub2zh-faithful-client"
$args = @(
  "-m", "PyInstaller",
  "--noconfirm",
  "--windowed",
  "--name", $distName,
  "--paths", "src",
  "scripts\\launch_gui.py"
)

if ($Clean) {
  $args += "--clean"
}
if ($OneFile) {
  $args += "--onefile"
}

Write-Host "[3/4] Build client..."
python @args

if (-not $OneFile) {
  Write-Host "[4/4] Copy docs/templates..."
  $dest = Join-Path "dist" $distName
  Copy-Item "README.md", "CONFIG_README.md", "config.yaml", "termbase.yaml" -Destination $dest -Force
  Write-Host "Built client at: $dest"
} else {
  Write-Host "Built single-file client at: dist\\$distName.exe"
}
