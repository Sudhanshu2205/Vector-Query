param(
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-AvailablePort {
    param(
        [Parameter(Mandatory = $true)]
        [int]$PreferredPort
    )

    for ($candidate = $PreferredPort; $candidate -lt ($PreferredPort + 20); $candidate++) {
        $listener = $null
        try {
            $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $candidate)
            $listener.Start()
            return $candidate
        }
        catch {
            continue
        }
        finally {
            if ($listener) {
                $listener.Stop()
            }
        }
    }

    throw "No free port found between $PreferredPort and $($PreferredPort + 19)."
}

function Test-Interpreter {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonPath
    )

    if (-not (Test-Path -LiteralPath $PythonPath)) {
        return $false
    }

    & $PythonPath -c "import importlib.util, sys; required=('fastapi','uvicorn','slowapi'); missing=[name for name in required if importlib.util.find_spec(name) is None]; raise SystemExit(0 if not missing else 1)"
    return $LASTEXITCODE -eq 0
}

$candidateInterpreters = @(
    (Join-Path $projectRoot ".conda-rag-env\python.exe"),
    (Join-Path $projectRoot ".venv\Scripts\python.exe"),
    $env:VECTORQUERY_PYTHON,
    "C:\Users\avish\anaconda3\envs\rag_env\python.exe"
) | Where-Object { $_ }

$pythonPath = $candidateInterpreters | Where-Object { Test-Interpreter $_ } | Select-Object -First 1

if (-not $pythonPath) {
    Write-Host ""
    Write-Host "No working Python interpreter was found for VectorQuery." -ForegroundColor Red
    Write-Host "Expected one of these environments to contain FastAPI, Uvicorn, and SlowAPI:" -ForegroundColor Yellow
    $candidateInterpreters | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""
    Write-Host "Recommended fix on this machine:" -ForegroundColor Yellow
    Write-Host "  conda activate rag_env"
    Write-Host "  .\run_vectorquery.ps1"
    exit 1
}

$resolvedPort = Get-AvailablePort -PreferredPort $Port
$arguments = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$resolvedPort")
if ($Reload) {
    $arguments += "--reload"
}

Write-Host "Using Python: $pythonPath" -ForegroundColor Green
Write-Host "Project root: $projectRoot" -ForegroundColor Green
if ($resolvedPort -ne $Port) {
    Write-Host "Requested port $Port was busy. Using port $resolvedPort instead." -ForegroundColor Yellow
}
Write-Host "Open the UI at: http://127.0.0.1:$resolvedPort/ui" -ForegroundColor Cyan
if ($Reload) {
    Write-Host "Mode: reload enabled" -ForegroundColor Yellow
}
else {
    Write-Host "Mode: single-process (recommended on this machine)" -ForegroundColor Yellow
}
Write-Host ""

Push-Location $projectRoot
try {
    & $pythonPath @arguments
}
finally {
    Pop-Location
}
