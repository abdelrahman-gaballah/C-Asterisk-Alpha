<div align="center">
  <img width="212" height="233" alt="C* Logo" src="https://github.com/user-attachments/assets/36b62d75-f20e-4bb3-a31b-c5fc696df045" />

  # C* (C-Asterisk)

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Python](https://img.shields.io/badge/Frontend-Python-blue.svg)](https://www.python.org/)
  [![LLVM](https://img.shields.io/badge/Backend-LLVM%20%2F%20llvmlite-red.svg)](https://llvmlite.readthedocs.io/)

  **The simplicity of Python. The speed of C++. The power of LLVM.**
</div>

---

## Quick Start

```bash
# One-command setup (Linux)
chmod +x setup.sh && ./setup.sh
source ~/.bashrc

# Run your first program
cstar examples/hello.cstar

# Or without the alias
python3 src/main.py examples/hello.cstar
```

**Windows** (PowerShell as Admin):
```powershell
.\setup.ps1
. $PROFILE
cstar examples\hello.cstar
```

**Prerequisites:** Python 3.9+, `pip install llvmlite`, a C compiler (gcc/clang on Linux, MSVC on Windows).

---

## What Is C*?

C* (pronounced *"C-Star"*) is a compiled, statically-typed programming language built from the ground up. The goal is simple: **you should never have to choose between readable code and fast code.**

Python is approachable — but slow. C++ is fast — but notoriously painful to write. C* occupies the ground between them: a clean, Python-inspired syntax that compiles directly to native machine code through the LLVM compiler infrastructure. The result is code that reads like a scripting language and runs at the speed of a systems language.

C* is directly inspired by **Mojo** (developed by Chris Lattner, the original creator of LLVM and Swift), which proved this architecture works at a professional level. C* is an independent, open-source exploration of the same core thesis — built from scratch.

```cstar
# A working neural network in C*
class NeuralNetwork {
    let weights: [float] = [0.5, -0.2, 0.1]
    let bias: float = 0.1

    func forward(x0: float, x1: float, x2: float) -> float {
        let sum: float = self.bias
        sum = sum + (x0 * self.weights[0])
        sum = sum + (x1 * self.weights[1])
        sum = sum + (x2 * self.weights[2])
        return 1.0 / (1.0 + exp(0.0 - sum))
    }
}

let ai = NeuralNetwork()
let p: float = ai.forward(1.5, 2.0, -1.0)
print(p)
```

---

## ⚡ Benchmarks

| Benchmark | Pure Python | NumPy | **C\* (LLVM JIT)** |
|---|---|---|---|
| MNIST Perceptron (100 images) | 0.860 s | — | **0.045 s (19x faster)** |
| Matrix Multiply 200x200 | 4.2 s | 0.003 s | **0.28 s (15x vs Python)** |
| Loop 50M iterations | 5.9 s | — | **0.15 s (39x faster)** |

Run your own:
```bash
python3 benchmarks/benchmark_runner.py --size 200
```

To prove C* isn't just theoretical, we implemented a **Single-Layer Perceptron** (a neural network) in pure C* and raced it against the mathematically identical implementation in pure Python — no NumPy, no PyTorch, no C++ libraries. Just raw math, compiled to native code.

```cstar
# The actual C* code that beat Python by 19x on MNIST
class NativeAI {
    let weights: [float] = [0.0, 0.0, ...]  # 400 weights
    let bias: float = 0.0
    let lr: float = 0.1

    func train() -> float {
        for epoch in 20 {
            for i in 100 {
                let sum: float = self.bias
                for p in 400 {
                    let idx: int = (i * 400) + p
                    sum = sum + (self.train_img[idx] * self.weights[p])
                }
                let pred: float = 1.0 / (1.0 + exp(0.0 - sum))
                let err: float = self.train_lbl[i] - pred
                for p in 400 {
                    let idx: int = (i * 400) + p
                    self.weights[p] = self.weights[p] + (self.lr * err * self.train_img[idx])
                }
                self.bias = self.bias + (self.lr * err)
            }
        }
        return 1.0
    }
}
```

---

## Language Features

### Variables & Type Annotations

Statically typed. Type annotations are optional when the type can be inferred.

```cstar
let x: int = 42
let pi: float = 3.14159
let name: string = "C-Star"
let flag: bool = true
```

### Arithmetic & Comparison Operators

All standard operators for `int` and `float`. Mixing types promotes int→float automatically.

```cstar
let sum: int = 10 + 3          # 13
let ratio: float = 10.0 / 3.0
let bigger: bool = 10 > 3      # true
let equal: bool = 10 == 3      # false
let not_equal: bool = 10 != 3  # true
let lte: bool = 3 <= 5        # true
```

### Strings

Concatenation with `+`, comparison with `==`/`!=`, escape sequences (`\n`, `\t`, `\"`, `\\`).

```cstar
let greeting: string = "Hello" + " " + "World"
let escaped: string = "line1\nline2\t\"quoted\""
```

### If / Else / While / For

```cstar
if score > 90 { print("A") } else { print("B") }

let i: int = 0
while i < 5 { print(i); i = i + 1 }

for i in 10 { print(i) }

let scores: [int] = [95, 87, 73, 100]
for s in scores { print(s) }
```

### Functions

```cstar
func add(a: int, b: int) -> int { return a + b }
func sigmoid(x: float) -> float {
    return 1.0 / (1.0 + exp(0.0 - x))
}
```

### Arrays (1D, 2D, 3D)

```cstar
let weights: [float] = [0.1, 0.5, -0.3, 0.9]
weights[2] = 0.77

let matrix: [[float]] = [[1.0, 2.0], [3.0, 4.0]]
let val: float = matrix[1][0]  # 3.0
```

### Classes & Methods

```cstar
class Counter {
    let count: int = 0
    func increment() -> int {
        self.count = self.count + 1
        return self.count
    }
}
let c = Counter()
c.increment()
print(c.count)  # 1
```

### Built-in Math & I/O

```cstar
let y: float = exp(2.0)         # e^2
let r: float = sqrt(144.0)      # 12.0
let l: float = log(2.718)       # ~1.0
let p: float = pow(2.0, 10.0)   # 1024.0
let data: [float] = load_csv("dataset.csv", 40000)
let t: float = get_time()
```

---

## Feature Overview

| Feature | Status |
|---|---|
| Variables (`let x: int = 5`) | ✅ |
| Type inference + int→float promotion | ✅ |
| Arithmetic: `+`, `-`, `*`, `/` | ✅ |
| Comparison: `==`, `!=`, `>`, `<`, `>=`, `<=` | ✅ |
| If/Else, While, For loops | ✅ |
| For-in-array iteration | ✅ |
| Functions with return types | ✅ |
| Classes with methods and `self` | ✅ |
| Arrays (1D, 2D, 3D) with index access | ✅ |
| Strings (concat `+`, compare `==`/`!=`, escape sequences) | ✅ |
| `print()`, `len()`, `abs()`, `round()` | ✅ |
| `exp()`, `sqrt()`, `log()`, `pow()` | ✅ |
| CSV loading via C FFI (`load_csv`) | ✅ |
| `free()` for manual memory management | ✅ |
| `get_time()` high-precision timer | ✅ |
| `import` module system | ✅ |
| Fast-math flags on all float operations | ✅ |
| `noalias` + `align` on pointer parameters | ✅ |
| LLVM `-O3` optimization pipeline | ✅ |
| JIT bitcode caching | ✅ |
| Panic-mode parser error recovery | ✅ |
| Cross-platform: Linux, Windows, macOS | ✅ |

---

## Performance Optimizations

C* applies these automatically to every compiled program:

1. **Fast-math flags** — Every `fadd`/`fsub`/`fmul`/`fdiv`/`fcmp` gets the `fast` flag, enabling FMA contraction, reassociation, and reciprocal approximation.
2. **`noalias` + `align 8`** — The `self` pointer and all array parameters are annotated, allowing LLVM's auto-vectorizer to emit SIMD instructions (AVX, AVX-512).
3. **`readnone`/`nounwind`** — Math functions (`exp`, `sqrt`, `pow`, `fabs`) are tagged so LLVM can hoist them out of loops.
4. **`-O3` pipeline** — Full inlining, loop unrolling, vectorization, and global value numbering.
5. **Format string deduplication** — Print format strings are emitted once regardless of usage count.
6. **Heap allocation for large arrays** — Class array fields >4KB use `malloc` instead of stack alloca.
7. **JIT caching** — Bitcode is cached by source hash; unchanged files skip re-compilation.

---

## Compiler CLI

```bash
python3 src/main.py <file.cstar>              # Compile + JIT + save .obj
python3 src/main.py <file.cstar> --no-exec     # Compile only (skip JIT)
python3 src/main.py <file.cstar> --ast         # Print the Abstract Syntax Tree
python3 src/main.py <file.cstar> -O0           # No optimization
python3 src/main.py <file.cstar> -O3           # Max optimization (default)
python3 src/main.py <file.cstar> --clean-cache # Purge cached bitcode
```

---

## How It Works — The Compiler Pipeline

Every `.cstar` file travels through five phases in order:

```
C* Source Code
      │
      ▼
┌─────────────┐
│   LEXER     │  Breaks raw text into a stream of typed tokens
└──────┬──────┘  (keywords, identifiers, operators, literals)
       │
       ▼
┌─────────────┐
│   PARSER    │  Consumes tokens via recursive descent and builds
└──────┬──────┘  an Abstract Syntax Tree (AST) — with panic-mode recovery
       │
       ▼
┌──────────────────┐
│ SEMANTIC ANALYZER│  Walks the AST: resolves scopes, checks types,
└──────┬───────────┘  validates function signatures, applies promotions
       │
       ▼
┌─────────────────┐
│  LLVM CODEGEN   │  Traverses the validated AST and emits LLVM IR
└──────┬──────────┘  with fast-math, noalias, and readnone annotations
       │
       ▼
┌─────────────┐
│  LLVM       │  Applies -O3 optimization passes and JIT-compiles
│  BACKEND    │  to native x86-64 machine code ⚡
└─────────────┘
```

The frontend (Lexer → Semantic Analyzer) is ~2,500 lines of pure Python — no parser generators, no ANTLR. The backend is LLVM, accessed through the `llvmlite` Python bindings — the same optimization passes used by Clang, Rust, and Swift.

---

## Project Structure

```
cstar/
├── src/
│   ├── main.py           # CLI entry point (argparse + __name__ guard)
│   ├── lexer.py          # Tokenizer with escape sequences
│   ├── parser.py         # Pratt parser with panic-mode error recovery
│   ├── semantic.py       # Type checker, symbol table, promotions
│   ├── codegen.py        # LLVM IR generation (fast-math, noalias)
│   ├── tokens.py         # Token type definitions
│   ├── errors.py         # Error hierarchy with line:column
│   ├── error_list.py     # Error accumulator
│   ├── visualizer.py     # ASCII AST printer
│   ├── lib_io.c          # C FFI: CSV loader, timer, thread pool
│   └── lib_io.so / .dll  # Compiled shared library
├── benchmarks/
│   ├── benchmark_runner.py  # Multi-language benchmark suite
│   └── matmul.cstar         # Matrix multiply benchmark (C*)
├── examples/                # 14 example .cstar programs
│   └── mnist_project/       # MNIST neural network + data
├── obj/                     # Compiled .obj + cached bitcode
├── setup.sh                 # Linux one-command setup
├── setup.ps1                # Windows one-command setup
├── .gitignore
└── README.md
```

---

## Internals

### C FFI (`src/lib_io.c`)

The native C library exposes three functions callable from C*:

| C Function | Used By | Purpose |
|---|---|---|
| `double get_time()` | `get_time()` builtin | Monotonic high-precision timer (nanosecond) |
| `double* load_csv_native(char*, int)` | `load_csv()` builtin | Fast CSV parser via `fread` + `strtod` |
| `void parallel_for(int, int, ...)` | — | pthread (Linux) / Windows Thread pool |

Compiled with: `gcc -O3 -march=native -ffast-math -fPIC -shared -o lib_io.so lib_io.c -lm -lpthread`

### Adding a New Built-in Function

1. **`src/semantic.py`** — Add name + return type to the `BUILTINS` dictionary
2. **`src/codegen.py`** — Declare the LLVM function in `__init__()`  
3. **`src/codegen.py`** — Handle the call in `visit_Call()` before the generic function lookup
4. Tag with `readnone` + `nounwind` attributes if the function has no side effects

---

## Origin & Contributing

C* started as a **college compiler construction project** — a practical exploration of the question: *how does a programming language actually work?* We built every phase from scratch: no parser generators, no ANTLR, no shortcuts. Every token, every AST node, every LLVM instruction was written by hand.

It grew into something we're genuinely proud of, so we're releasing it under the **MIT License** as an open-source project. Whether you're learning how compilers work, want to contribute a new language feature, or just want to see a working LLVM pipeline written in plain Python, you're welcome here.

**To contribute:**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-language-feature`)
3. Make your changes and ensure all examples compile: `for f in examples/*.cstar; do python3 src/main.py "$f" --no-exec; done`
4. Open a pull request with a description of what you built

Ideas for contributions: a standard library, better error messages with source code highlighting, generic type support, or a language server protocol (LSP) implementation.

---

## License

MIT © The C* Team. See [LICENSE](LICENSE) for details.

---

<div align="center">
  <sub>Built from scratch. Compiled to metal. Faster than Python.</sub>
</div>
