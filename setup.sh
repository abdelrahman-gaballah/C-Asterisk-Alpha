#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
#  C* (C-Asterisk) — One-command Linux Setup
# ──────────────────────────────────────────────────────────────

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[C*]${NC} $1"; }
ok()    { echo -e "${GREEN}[ OK]${NC} $1"; }
err()   { echo -e "${RED}[FAIL]${NC} $1"; }

info "C* Setup — Linux"

# ── 1. Check Python 3 ──
if command -v python3 &>/dev/null; then
    ok "python3 found: $(python3 --version)"
else
    err "python3 is required. Install it and re-run."
    exit 1
fi

# ── 2. Check / install llvmlite ──
if python3 -c "import llvmlite" 2>/dev/null; then
    ok "llvmlite $(python3 -c 'import llvmlite; print(llvmlite.__version__)')"
else
    info "Installing llvmlite (pip) ..."
    pip3 install llvmlite --break-system-packages 2>/dev/null || pip3 install llvmlite
    if python3 -c "import llvmlite" 2>/dev/null; then
        ok "llvmlite installed"
    else
        err "llvmlite installation failed. Try: pip3 install llvmlite"
        exit 1
    fi
fi

# ── 3. Check C compiler ──
CC=""
for c in gcc clang; do
    if command -v "$c" &>/dev/null; then
        CC="$c"
        break
    fi
done
if [ -n "$CC" ]; then
    ok "C compiler found: $CC ($($CC --version | head -1))"
else
    err "No C compiler found (gcc or clang). Install build-essential."
    exit 1
fi

# ── 4. Compile lib_io.so ──
LIB_DIR="$(dirname "$0")/src"
LIB_SRC="$LIB_DIR/lib_io.c"
LIB_OUT="$LIB_DIR/lib_io.so"

if [ -f "$LIB_SRC" ]; then
    info "Compiling lib_io.so ..."
    $CC -O3 -march=native -ffast-math -fPIC -shared \
        -o "$LIB_OUT" "$LIB_SRC" -lm -lpthread
    if [ -f "$LIB_OUT" ]; then
        ok "lib_io.so compiled"
    else
        err "lib_io.so compilation failed"
        exit 1
    fi
else
    info "lib_io.c not found at $LIB_SRC — skipping"
fi

# ── 5. Create obj/ directory ──
mkdir -p "$(dirname "$0")/obj"
ok "obj/ directory ready"

# ── 6. Optional: add cstar alias ──
if ! grep -q 'alias cstar=' ~/.bashrc 2>/dev/null; then
    echo -e "\n# C* alias" >> ~/.bashrc
    echo "alias cstar='python3 $(cd "$(dirname "$0")" && pwd)/src/main.py'" >> ~/.bashrc
    ok "Alias added: cstar <file.cstar>  (restart shell or run 'source ~/.bashrc')"
else
    info "cstar alias already present in ~/.bashrc"
fi

# ── 7. Verify ──
echo ""
python3 "$(dirname "$0")/src/main.py" --help 2>/dev/null | head -2
echo ""
ok "C* is ready. Try:  cstar examples/hello.cstar"
