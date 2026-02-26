# Build Windows Installer Script - Pure Python Version
# Creates a self-extracting installer using Python only

param(
  [switch]$Clean,
  [switch]$SkipClientBuild
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

function Get-AppVersion {
  $content = Get-Content (Join-Path $root "pyproject.toml") -Raw
  if ($content -match 'version\s*=\s*"([^"]+)"') {
    return $Matches[1]
  }
  return "0.1.0"
}

if (-not $SkipClientBuild) {
  Write-Host "[1/3] Build PyInstaller client..." -ForegroundColor Cyan
  & (Join-Path $PSScriptRoot "build_windows_client.ps1") -Clean:$Clean
} else {
  Write-Host "[1/3] Skip client build." -ForegroundColor Cyan
}

$clientDir = Join-Path $root "dist\epub2zh-faithful-client"
if (-not (Test-Path $clientDir)) {
  throw "Client folder not found: $clientDir"
}

$version = Get-AppVersion
$outputDir = Join-Path $root "dist\installer"
$outputFile = Join-Path $outputDir "epub2zh-faithful-client-setup-$version.exe"

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

Write-Host "[2/3] Creating installer using Python..." -ForegroundColor Cyan

$pythonScript = @"
import os
import zipfile
import tempfile
import shutil
from pathlib import Path

root = Path("$root")
client_dir = root / "dist" / "epub2zh-faithful-client"
output_dir = root / "dist" / "installer"
version = "$version"
output_file = output_dir / f"epub2zh-faithful-client-setup-{version}.exe"

output_dir.mkdir(parents=True, exist_ok=True)

python_exe = Path("F:/Python314/python.exe")
if not python_exe.exists():
    python_exe = Path(shutil.which("python.exe"))

if not python_exe:
    print("Python not found!")
    exit(1)

print(f"[3/3] Building installer: {output_file}")

temp_dir = Path(tempfile.mkdtemp())
extract_dir = temp_dir / "extract"
extract_dir.mkdir()

for item in client_dir.iterdir():
    if item.name in ["cache.sqlite", "cache.sqlite-journal"]:
        continue
    dest = extract_dir / item.name
    if item.is_file():
        shutil.copy2(item, dest)
    else:
        shutil.copytree(item, dest)

config_txt = extract_dir / "install_config.txt"
config_txt.write_text(f"""# Install Configuration
AppTitle=epub2zh-faithful-client {version}
InstallDir={{autopf}}\\epub2zh-faithful-client
Launcher=epub2zh-faithful-client.exe
""", encoding="utf-8")

installer_exe = temp_dir / "installer_builder.exe"
builder_code = '''
import os
import sys
import zipfile
import tempfile
import shutil
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        install_dir = os.path.join(os.environ.get("PROGRAMFILES", "C:\\\\Program Files"), "epub2zh-faithful-client")
    else:
        install_dir = sys.argv[1]
    
    temp_dir = Path(tempfile.gettempdir()) / "epub2zh-installer"
    temp_dir.mkdir(exist_ok=True)
    
    archive = temp_dir / "client.7z"
    
    with zipfile.ZipFile(archive, "r") as zip_ref:
        zip_ref.extractall(temp_dir)
    
    os.makedirs(install_dir, exist_ok=True)
    for item in (temp_dir / "extract").iterdir():
        dest = Path(install_dir) / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    
    launcher = Path(install_dir) / "epub2zh-faithful-client.exe"
    if launcher.exists():
        print(f"Installation complete! Launching {launcher}")
        os.startfile(str(launcher))
    
    shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
'''

(temp_dir / "builder.py").write_text(builder_code, encoding="utf-8")

with zipfile.ZipFile(output_dir / "installer_data.zip", "w", zipfile.ZIP_DEFLATED) as zipf:
    for root_dir, dirs, files in os.walk(extract_dir):
        for file in files:
            file_path = Path(root_dir) / file
            arcname = file_path.relative_to(temp_dir)
            zipf.write(file_path, arcname)

pyinstaller_args = [
    str(python_exe), "-m", "PyInstaller",
    "--onefile",
    "--windowed",
    "--name", f"epub2zh-faithful-setup-{version}",
    "--icon=NONE",
    "--add-data", f"{output_dir / 'installer_data.zip'}{os.pathsep}.",
    str(temp_dir / "builder.py")
]

print(f"Running PyInstaller to create single exe...")
os.system(" ".join(pyinstaller_args))

dist_exe = Path(f"dist/epub2zh-faithful-setup-{version}.exe")
if dist_exe.exists():
    shutil.move(str(dist_exe), str(output_file))
    print(f"Installer created: {output_file}")
    print(f"Size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
else:
    print("Failed to create installer")

shutil.rmtree(temp_dir, ignore_errors=True)
if (output_dir / "installer_data.zip").exists():
    (output_dir / "installer_data.zip").unlink()
"""

python -c "$pythonScript"

Write-Host "[3/3] Done!" -ForegroundColor Green

if (Test-Path $outputFile) {
  Write-Host "Installer: $outputFile" -ForegroundColor Green
  Write-Host "Size: $([math]::Round((Get-Item $outputFile).Length / 1MB, 2)) MB" -ForegroundColor Green
} else {
  Write-Host "Installer creation failed" -ForegroundColor Red
  exit 1
}
