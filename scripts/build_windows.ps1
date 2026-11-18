<#
.SYNOPSIS
    Reproducible Windows build script for AgentVid — AI Video Creation & Editing Studio.
    Builds:
      1. Custom AgentVid icons & installer bitmaps
      2. Standalone Python AI/Video Engine (dist-engine/agentvid-engine/agentvid-engine.exe)
      3. Standalone Windows Desktop App + NSIS Installer (dist-desktop/AgentVid-Setup-1.0.0-x64.exe)
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    throw "Python virtual environment not found at $Py. Run: python -m venv .venv && .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

Write-Host "`n[1/3] Generating AgentVid brand icons and installer bitmaps..." -ForegroundColor Cyan
& $Py (Join-Path $Root "scripts\generate_brand_assets.py")

Write-Host "`n[2/3] Building standalone AgentVid local AI & FFmpeg engine via PyInstaller..." -ForegroundColor Cyan
$DistEngine = Join-Path $Root "dist-engine"
$BuildWork = Join-Path $Root "build-engine"
if (Test-Path $DistEngine) { Remove-Item -Recurse -Force $DistEngine }
if (Test-Path $BuildWork) { Remove-Item -Recurse -Force $BuildWork }

& $Py -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --console `
    --name agentvid-engine `
    --distpath $DistEngine `
    --workpath $BuildWork `
    --specpath $BuildWork `
    --hidden-import uvicorn.logging `
    --hidden-import uvicorn.loops `
    --hidden-import uvicorn.loops.auto `
    --hidden-import uvicorn.protocols `
    --hidden-import uvicorn.protocols.http `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.websockets `
    --hidden-import uvicorn.protocols.websockets.auto `
    --hidden-import uvicorn.lifespan `
    --hidden-import uvicorn.lifespan.on `
    --hidden-import sqlalchemy.dialects.sqlite `
    --hidden-import multipart `
    --hidden-import soundfile `
    --collect-data soundfile `
    --collect-binaries soundfile `
    --collect-all sherpa_onnx `
    --collect-all sherpa_onnx_core `
    --collect-submodules studio `
    (Join-Path $Root "studio\agentvid_entry.py")

Write-Host "`n[3/3] Packaging standalone AgentVid Windows desktop executable & NSIS installer..." -ForegroundColor Cyan
Set-Location (Join-Path $Root "desktop")
$LocalElectron = Join-Path $Root "desktop\node_modules\electron\dist"
if (Test-Path $LocalElectron) {
    & (Join-Path $Root "desktop\node_modules\.bin\electron-builder.cmd") --win --x64 "-c.electronDist=$LocalElectron"
} else {
    & npm.cmd run build:win
}

Write-Host "`nAgentVid Windows build complete!" -ForegroundColor Green
Get-ChildItem (Join-Path $Root "dist-desktop") | Select-Object Name, Length | Format-Table -AutoSize
