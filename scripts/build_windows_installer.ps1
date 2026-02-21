param(
  [switch]$Clean,
  [switch]$SkipClientBuild
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

function Get-IsccPath {
  $candidates = @(
    $env:ISCC_PATH,
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
  )

  $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source) {
    $candidates = @($cmd.Source) + $candidates
  }

  foreach ($path in $candidates) {
    if ($path -and (Test-Path $path)) {
      return $path
    }
  }
  return $null
}

function Get-AppVersion {
  $content = Get-Content (Join-Path $root "pyproject.toml") -Raw
  if ($content -match 'version\s*=\s*"([^"]+)"') {
    return $Matches[1]
  }
  return "0.1.0"
}

$iscc = Get-IsccPath
if (-not $iscc) {
  throw "ISCC.exe not found. Install Inno Setup 6 first (e.g. C:\Users\<you>\AppData\Local\Programs\Inno Setup 6\ISCC.exe)."
}

if (-not $SkipClientBuild) {
  Write-Host "[1/3] Build PyInstaller client..."
  & (Join-Path $PSScriptRoot "build_windows_client.ps1") -Clean:$Clean
} else {
  Write-Host "[1/3] Skip client build."
}

$clientDir = Join-Path $root "dist\epub2zh-faithful-client"
if (-not (Test-Path $clientDir)) {
  throw "Client folder not found: $clientDir"
}

$version = Get-AppVersion
$outputDir = Join-Path $root "dist\installer"
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

$issPath = Join-Path $PSScriptRoot "windows_installer.iss"

Write-Host "[2/3] Build installer with Inno Setup..."
& $iscc `
  "/DMyAppVersion=$version" `
  "/DMySourceDir=$clientDir" `
  "/DMyOutputDir=$outputDir" `
  "/DMyOutputBaseName=epub2zh-faithful-client-setup" `
  $issPath

Write-Host "[3/3] Done."
Write-Host "Installer: $(Join-Path $outputDir 'epub2zh-faithful-client-setup.exe')"
