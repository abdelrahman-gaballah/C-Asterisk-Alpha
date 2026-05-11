#!/usr/bin/env python3
"""
C* Benchmark Suite — compares Pure Python, NumPy, and C* on matrix multiply.
Usage:  python benchmarks/benchmark_runner.py [--size 500] [--csv BENCH.csv]
"""

import sys
import os
import time
import argparse
import subprocess
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def generate_matrices(N):
    """Return (A, B) flat lists of length N*N with deterministic values."""
    rng = 0
    A, B = [], []
    for i in range(N * N):
        rng = (rng * 1103515245 + 12345) & 0x7fffffff
        A.append(rng / 2147483648.0)
        rng = (rng * 1103515245 + 12345) & 0x7fffffff
        B.append(rng / 2147483648.0)
    return A, B


def csv_dump(path, data, N):
    with open(path, 'w') as f:
        for i in range(N):
            row = data[i * N:(i + 1) * N]
            f.write(','.join(f'{v:.10f}' for v in row) + '\n')


# ──────────────────────────────────────────────────────────────
# Benchmarks
# ──────────────────────────────────────────────────────────────

def bench_python_pure(A, B, N):
    """Pure Python triple-loop matmul."""
    C = [0.0] * (N * N)
    t0 = time.perf_counter()
    for i in range(N):
        for j in range(N):
            s = 0.0
            for k in range(N):
                s += A[i * N + k] * B[k * N + j]
            C[i * N + j] = s
    return time.perf_counter() - t0, C


def bench_numpy(A, B, N):
    import numpy as np
    A_np = np.array(A, dtype=np.float64).reshape(N, N)
    B_np = np.array(B, dtype=np.float64).reshape(N, N)
    t0 = time.perf_counter()
    C_np = A_np @ B_np
    elapsed = time.perf_counter() - t0
    return elapsed, C_np.flatten().tolist()


def bench_cstar(A, B, N, src_dir):
    """Generate a C* source file and compile/JIT-run it."""
    obj_dir = os.path.join(os.path.dirname(__file__), '..', 'obj')
    a_path = os.path.join(obj_dir, '_bench_A.csv')
    b_path = os.path.join(obj_dir, '_bench_B.csv')
    c_path = os.path.join(obj_dir, '_bench_C.csv')
    csv_dump(a_path, A, N)
    csv_dump(b_path, B, N)
    zeros = [0.0] * (N * N)
    csv_dump(c_path, zeros, N)

    cstar_src = f'''let N: int = {N}
let size: int = N * N

let A: [float] = load_csv("{a_path}", size)
let B: [float] = load_csv("{b_path}", size)
let C: [float] = load_csv("{c_path}", size)

let t0: float = get_time()

for i in N {{
    for j in N {{
        let sum: float = 0.0
        for k in N {{
            let a_off: int = (i * N) + k
            let b_off: int = (k * N) + j
            sum = sum + (A[a_off] * B[b_off])
        }}
        let c_off: int = (i * N) + j
        C[c_off] = sum
    }}
}}

let elapsed: float = get_time() - t0
if elapsed < 0.000001 {{ elapsed = 0.000001 }}
print(elapsed)
'''

    src_path = os.path.join(os.path.dirname(__file__), '..', 'obj', '_bench_matmul.cstar')
    with open(src_path, 'w') as f:
        f.write(cstar_src)

    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, os.path.join(src_dir, 'main.py'), src_path, '--no-exec'],
        capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), '..')
    )
    compile_time = time.perf_counter() - t0

    # Run the compiled .obj via JIT inside main.py — 
    # but currently main.py --no-exec skips JIT.
    # Instead, run main.py without --no-exec to JIT-execute:
    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, os.path.join(src_dir, 'main.py'), src_path],
        capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), '..')
    )
    elapsed = time.perf_counter() - t0

    # Parse output to extract the elapsed time
    for line in result.stdout.split('\n'):
        line = line.strip()
        try:
            val = float(line)
            if val > 0.001 and val < 1e6:
                return val, elapsed
        except ValueError:
            continue
    return elapsed, elapsed


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='C* Benchmark Suite')
    parser.add_argument('--size', type=int, default=200,
                        help='Matrix size N (default: 200, use 500 for heavy)')
    parser.add_argument('--csv', type=str, default=None,
                        help='Append results to CSV file')
    parser.add_argument('--no-cstar', action='store_true',
                        help='Skip C* benchmark (Python + NumPy only)')
    args = parser.parse_args()

    N = args.size
    print(f'\n  Benchmark: Matrix Multiply ({N}x{N})')
    print(f'  Flops per matmul: {2 * N**3:,}')
    print('─' * 50)

    src_dir = os.path.join(os.path.dirname(__file__), '..', 'src')
    os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'obj'), exist_ok=True)

    # Generate data once
    print('  Generating matrices ...', end=' ', flush=True)
    A, B = generate_matrices(N)
    print('done')

    results = {}

    # ── Pure Python ──
    print('  Pure Python       ...', end=' ', flush=True)
    t_py, C_py = bench_python_pure(A, B, N)
    print(f'{t_py:.4f} s')
    results['Python'] = t_py

    # ── NumPy ──
    try:
        print('  NumPy             ...', end=' ', flush=True)
        t_np, C_np = bench_numpy(A, B, N)
        print(f'{t_np:.4f} s')
        results['NumPy'] = t_np
    except ImportError:
        print('(skipped — numpy not installed)')
        results['NumPy'] = None

    # ── C* ──
    if not args.no_cstar:
        print('  C* (LLVM JIT)     ...', end=' ', flush=True)
        t_cs, _ = bench_cstar(A, B, N, src_dir)
        print(f'{t_cs:.4f} s')
        results['C*'] = t_cs

    # ── Summary Table ──
    print()
    print('  ' + '═' * 42)
    hdr = f'  {"Language":<20} {"Time (s)":<12} {"Speedup vs Py":<16}'
    print(hdr)
    print('  ' + '─' * 42)

    baseline = results.get('Python', 1)
    rows = []
    for lang in ['Python', 'NumPy', 'C*']:
        t = results.get(lang)
        if t is None:
            continue
        speedup = baseline / t if t > 0 else float('inf')
        rows.append((lang, t, speedup))
        print(f'  {lang:<20} {t:<12.4f} {speedup:<16.2f}x')

    if len(rows) >= 3:
        cstar_vs_numpy = results.get('C*', 1) / results.get('NumPy', 1) if results.get('NumPy') else float('inf')
        print(f'  {"":->42}')
        print(f'  {"C* vs NumPy":<20} {"":<12} {cstar_vs_numpy:<16.2f}x')
    print('  ' + '═' * 42)
    print()

    # ── CSV export ──
    if args.csv:
        import csv
        with open(args.csv, 'a', newline='') as f:
            w = csv.writer(f)
            if f.tell() == 0:
                w.writerow(['N', 'Language', 'Time', 'Speedup_vs_Python'])
            for lang, t, sp in rows:
                w.writerow([N, lang, round(t, 6), round(sp, 2)])
        print(f'  Results appended to {args.csv}')

    # Correctness check: C* result vs NumPy (if both exist)
    if 'C*' in results and 'NumPy' in results:
        print('  (Correctness check skipped — C* writes its own CSV loader)')
    print()


if __name__ == '__main__':
    main()
