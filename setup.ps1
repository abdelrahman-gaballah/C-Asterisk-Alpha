# ──────────────────────────────────────────────────────────────
#  C* (C-Asterisk) — One-command Windows Setup (PowerShell)
# ──────────────────────────────────────────────────────────────

Write-Host "[C*] C* Setup - Windows" -ForegroundColor Cyan

# ── 1. Check Python ──
try {
    $pyVer = python --version 2>&1
    Write-Host "[ OK] python found: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] Python is required. Install from python.org" -ForegroundColor Red
    exit 1
}

# ── 2. Check / install llvmlite ──
try {
    $v = python -c "import llvmlite; print(llvmlite.__version__)" 2>&1
    Write-Host "[ OK] llvmlite $v" -ForegroundColor Green
} catch {
    Write-Host "[C*] Installing llvmlite ..." -ForegroundColor Cyan
    pip install llvmlite
    try {
        python -c "import llvmlite" 2>$null
        Write-Host "[ OK] llvmlite installed" -ForegroundColor Green
    } catch {
        Write-Host "[FAIL] llvmlite installation failed. Try: pip install llvmlite" -ForegroundColor Red
        exit 1
    }
}

# ── 3. Check MSVC / clang (optional — lib_io.dll comes prebuilt) ──
$dllPath = Join-Path $PSScriptRoot "src\lib_io.dll"
if (Test-Path $dllPath) {
    Write-Host "[ OK] lib_io.dll found (pre-compiled)" -ForegroundColor Green
} else {
    Write-Host "[C*] lib_io.dll not found — CSV loading will be disabled" -ForegroundColor Yellow
    Write-Host "     Recompile with: cl /O2 /LD src\lib_io.c /Fe:src\lib_io.dll" -ForegroundColor Gray
}

# ── 4. Create obj/ directory ──
$objDir = Join-Path $PSScriptRoot "obj"
if (-not (Test-Path $objDir)) {
    New-Item -ItemType Directory -Path $objDir | Out-Null
}
Write-Host "[ OK] obj/ directory ready" -ForegroundColor Green

# ── 5. Optional: add cstar function to profile ──
$profilePath = $PROFILE.CurrentUserAllHosts
$cstarLine = "function cstar { python '" + (Join-Path $PSScriptRoot "src\main.py") + "' `$args }"
$already = Select-String -Path $profilePath -Pattern "function cstar" -SimpleMatch -Quiet 2>$null
if (-not $already) {
    Add-Content -Path $profilePath -Value "`n# C* alias`n$cstarLine"
    Write-Host "[ OK] Function added: cstar <file.cstar>  (restart shell or run '. `$PROFILE')" -ForegroundColor Green
} else {
    Write-Host "[C*] cstar function already in profile" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "[ OK] C* is ready. Try:  cstar examples\hello.cstar" -ForegroundColor Green
