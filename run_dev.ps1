# Garden City Fine Cuts — local dev server (port configured below)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Port = 18080
$Bind = "127.0.0.1"

Write-Host "Starting Django at http://${Bind}:${Port}/"
& .\.venv\Scripts\python.exe manage.py runserver "${Bind}:${Port}"
