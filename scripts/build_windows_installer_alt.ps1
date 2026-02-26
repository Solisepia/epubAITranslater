# Build Windows Installer Script
# Uses 7-Zip SFX to create installer without Inno Setup

param(
  [switch]$Clean,
  [switch]$SkipClientBuild
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

function Find-7Zip {
  $paths = @(
    "C:\Program Files\7-Zip\7z.exe",
    "C:\Program Files (x86)\7-Zip\7z.exe",
    "$env:ProgramFiles\7-Zip\7z.exe"
  )
  
  foreach ($path in $paths) {
    if (Test-Path $path) {
      return $path
    }
  }
  
  $sevenZip = Get-Command 7z.exe -ErrorAction SilentlyContinue
  if ($sevenZip) {
    return $sevenZip.Source
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

$sevenZip = Find-7Zip
if (-not $sevenZip) {
  Write-Host "7-Zip not found. Please install 7-Zip from https://www.7-zip.org/" -ForegroundColor Yellow
  Write-Host "Alternatively, install Inno Setup 6 for full installer support." -ForegroundColor Yellow
  exit 1
}

if (-not $SkipClientBuild) {
  Write-Host "[1/4] Build PyInstaller client..." -ForegroundColor Cyan
  & (Join-Path $PSScriptRoot "build_windows_client.ps1") -Clean:$Clean
} else {
  Write-Host "[1/4] Skip client build." -ForegroundColor Cyan
}

$clientDir = Join-Path $root "dist\epub2zh-faithful-client"
if (-not (Test-Path $clientDir)) {
  throw "Client folder not found: $clientDir"
}

$version = Get-AppVersion
$outputDir = Join-Path $root "dist\installer"
$outputFile = Join-Path $outputDir "epub2zh-faithful-client-setup-$version.exe"
$tempZip = Join-Path $outputDir "temp-installer.zip"

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

Write-Host "[2/4] Create 7-Zip SFX installer..." -ForegroundColor Cyan

$7zConfig = @"
;!@Install@!UTF-8!
Title="epub2zh-faithful-client $version"
RunProgram="epub2zh-faithful-client.exe"
GUIMode="2"
;!@InstallEnd@!
"@

$configFile = Join-Path $outputDir "7z.sfx.config"
$7zConfig | Out-File -FilePath $configFile -Encoding UTF8

$sfxModule = Join-Path (Split-Path $sevenZip) "7z.sfx"
if (-not (Test-Path $sfxModule)) {
  Write-Host "7z.sfx module not found. Creating ZIP archive instead." -ForegroundColor Yellow
  & $sevenZip a -tzip $tempZip "$clientDir\*" -r | Out-Null
  Rename-Item -Path $tempZip -NewName (Split-Path $outputFile -Leaf) -Force
  Write-Host "[4/4] Done. Created ZIP archive: $outputFile" -ForegroundColor Green
  exit 0
}

Write-Host "[3/4] Copy client files to temp directory..." -ForegroundColor Cyan

$tempExtractDir = Join-Path $outputDir "temp-extract"
if (Test-Path $tempExtractDir) {
  Remove-Item -Path $tempExtractDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempExtractDir -Force | Out-Null
Copy-Item -Path "$clientDir\*" -Destination $tempExtractDir -Recurse -Force

Write-Host "[4/4] Building SFX installer..." -ForegroundColor Cyan

$7zArgs = @(
  "a"
  "-r"
  "-m0=Copy"
  $tempZip
  "$tempExtractDir\*"
)

& $sevenZip $7zArgs | Out-Null

$tempSfx = Join-Path $outputDir "temp-sfx.exe"
Copy-Item -Path $sfxModule -Destination $tempSfx -Force
Get-Content -Path $configFile -Encoding UTF8 -Raw | Out-File -FilePath $tempSfx -Encoding UTF8 -Append
Get-Content -Path $tempZip -Encoding Byte | Out-File -FilePath $tempSfx -Encoding Byte -Append

Move-Item -Path $tempSfx -Destination $outputFile -Force

Remove-Item -Path $tempZip -Force
Remove-Item -Path $configFile -Force
Remove-Item -Path $tempExtractDir -Recurse -Force

Write-Host "Installer created: $outputFile" -ForegroundColor Green
Write-Host "Size: $([math]::Round((Get-Item $outputFile).Length / 1MB, 2)) MB" -ForegroundColor Green
