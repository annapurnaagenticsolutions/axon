# AXON Hero GIF Generator — PowerShell Version
# Uses Windows Terminal + screen capture (no external tools needed)
#
# Usage:
#   .\scripts\generate_hero_gif.ps1
#
# Requirements:
#   - screenToGif (https://www.screentogif.com/) — free, portable
#   - OR: ShareX (https://getsharex.com/) — free, includes GIF capture
#
# This script opens a terminal, runs the AXON demo commands,
# and tells you exactly when to start/stop screen capture.

param(
    [string]$AxonDir = "d:\vision_agentic\annapurnaagenticsolutions\axon"
)

$ErrorActionPreference = "Stop"

Write-Host "=== AXON Hero GIF Generator (PowerShell) ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "Before starting, install one of:" -ForegroundColor Yellow
Write-Host "  - ScreenToGif: https://www.screentogif.com/ (recommended, portable)"
Write-Host "  - ShareX: https://getsharex.com/"
Write-Host ""
Write-Host "Press any key when your recorder is ready..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

Set-Location $AxonDir
Write-Host ""
Write-Host ">>> START RECORDING NOW <<<" -ForegroundColor Red
Start-Sleep -Seconds 1

function Write-Step($label, $color = "Cyan") {
    Write-Host ""
    Write-Host $label -ForegroundColor $color
    Start-Sleep -Milliseconds 600
}

# Header
Write-Host "=== AXON - Typed DSL for Autonomous Agents ===" -ForegroundColor Cyan
Write-Host "Compiles to Python + TypeScript" -ForegroundColor DarkGray
Start-Sleep -Milliseconds 800

# Show .ax file
Write-Step "cat examples/hello.ax"
Get-Content examples/hello.ax
Start-Sleep -Milliseconds 1000

# Syntax check
Write-Step "axon syntax examples/hello.ax"
python -m axon syntax examples/hello.ax
Start-Sleep -Milliseconds 800

# Validate
Write-Step "axon validate examples/hello.ax"
python -m axon validate examples/hello.ax
Start-Sleep -Milliseconds 800

# Run with mock
Write-Step "axon run examples/hello.ax --mock"
python -m axon run examples/hello.ax --mock
Start-Sleep -Milliseconds 1000

# Compile to TypeScript
Write-Step "axon compile examples/hello.ax --target ts"
python -m axon compile examples/hello.ax --target ts
Start-Sleep -Milliseconds 1000

# Closing
Write-Host ""
Write-Host "One language. Many worlds." -ForegroundColor Cyan
Write-Host "github.com/annapurna-agentics/axon" -ForegroundColor DarkGray
Start-Sleep -Milliseconds 1500

Write-Host ""
Write-Host ">>> STOP RECORDING NOW <<<" -ForegroundColor Red
Write-Host "Save as: docs/launch/axon-hero.gif" -ForegroundColor Yellow
Write-Host "Target: <5MB, 15-20s, 800x400 or 1200x600" -ForegroundColor Yellow
