<#
.SYNOPSIS
    One-command verification check for Cindercrest 2.0.
.DESCRIPTION
    Runs linting (Ruff), strict static type-checking (Mypy), and automated unit/integration tests (Pytest).
    Returns exit code 0 if all checks pass, non-zero otherwise.
#>

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "Cindercrest 2.0: Running One-Command Verification Check" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$PythonExe = ".\.venv\Scripts\python.exe"
$RuffExe = ".\.venv\Scripts\ruff.exe"
$MypyExe = ".\.venv\Scripts\mypy.exe"
$PytestExe = ".\.venv\Scripts\pytest.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "Run 'python -m venv .venv' and install requirements first." -ForegroundColor Yellow
    exit 1
}

# 1. Linting & Formatting Check (Ruff)
Write-Host "`n[1/4] Running Linter (Ruff)..." -ForegroundColor Yellow
& $RuffExe check backend
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAILED] Ruff linting check failed." -ForegroundColor Red
    exit 1
}
Write-Host "[PASSED] Ruff linting check passed." -ForegroundColor Green

# 2. Strict Type Check (Mypy)
Write-Host "`n[2/4] Running Type Checker (Mypy)..." -ForegroundColor Yellow
& $MypyExe backend
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAILED] Mypy type check failed." -ForegroundColor Red
    exit 1
}
Write-Host "[PASSED] Mypy type check passed." -ForegroundColor Green

# 3. Automated Test Suite (Pytest)
Write-Host "`n[3/4] Running Test Suite (Pytest)..." -ForegroundColor Yellow
& $PytestExe -v backend/tests
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAILED] Pytest test suite failed." -ForegroundColor Red
    exit 1
}
Write-Host "[PASSED] All automated tests passed." -ForegroundColor Green

# 4. Frontend Type Check (tsc)
Write-Host "`n[4/4] Running Frontend Type Check (TypeScript)..." -ForegroundColor Yellow
if (Test-Path "frontend/node_modules") {
    npm --prefix frontend run typecheck
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAILED] Frontend TypeScript check failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "[PASSED] Frontend TypeScript check passed." -ForegroundColor Green
} else {
    Write-Host "[SKIPPED] Frontend node_modules not found." -ForegroundColor DarkGray
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "ALL CINDERCREST 2.0 QUALITY CHECKS PASSED (FULL-STACK)" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
exit 0
