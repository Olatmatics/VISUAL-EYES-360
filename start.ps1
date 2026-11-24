# VISUAL EYES 360 - one-click local launcher
# Starts the FastAPI backend (port 8000) and the Vite web app (port 5173).
# Usage:  powershell -ExecutionPolicy Bypass -File .\start.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$web = Join-Path $root "web"

Write-Host "=============================================="
Write-Host "  VISUAL EYES 360 - Fuel Station Automation"
Write-Host "=============================================="

function Test-Port([int]$port) {
    try {
        $conn = Test-NetConnection -ComputerName 127.0.0.1 -Port $port -WarningAction SilentlyContinue -InformationLevel Quiet
        return $conn
    } catch {
        return $false
    }
}

# --- Backend ---
if (Test-Port 8000) {
    Write-Host "[backend]  already running on http://127.0.0.1:8000"
} else {
    Write-Host "[backend]  starting on http://127.0.0.1:8000 ..."
    $py = Join-Path $backend ".venv\Scripts\python.exe"
    Start-Process -FilePath $py `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload" `
        -WorkingDirectory $backend `
        -WindowStyle Minimized
}

# --- Frontend ---
if (Test-Port 5173) {
    Write-Host "[web]      already running on http://127.0.0.1:5173"
} else {
    Write-Host "[web]      starting on http://127.0.0.1:5173 ..."
    Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "npm run dev" `
        -WorkingDirectory $web `
        -WindowStyle Minimized
}

Write-Host ""
Write-Host "  Web app      : http://127.0.0.1:5173"
Write-Host "  Backend API  : http://127.0.0.1:8000"
Write-Host "  API docs     : http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "  First run?   : http://127.0.0.1:5173/setup  (token: change-this-setup-token)"
Write-Host "  Demo admin   : SUPERADMIN001 / Admin@1234"
Write-Host "  Demo manager : MGR001 / Manager@5678"
Write-Host ""
