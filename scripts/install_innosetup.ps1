# Download and Install Inno Setup 6
$ErrorActionPreference = "Stop"

$url = "https://jrsoftware.org/download.php/is.exe"
$output = "$env:TEMP\is-setup.exe"

Write-Host "Downloading Inno Setup 6..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $url -OutFile $output -UseBasicParsing

Write-Host "Installing Inno Setup 6..." -ForegroundColor Cyan
Start-Process -Wait -FilePath $output -ArgumentList "/VERYSILENT /ALLUSERS /SUPPRESSMSGBOXES"

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "ISCC.exe location: C:\Program Files (x86)\Inno Setup 6\ISCC.exe" -ForegroundColor Yellow

Remove-Item $output -Force
