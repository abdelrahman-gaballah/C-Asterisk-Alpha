import sys
import os
import platform
import subprocess
import re
import hashlib
import argparse

from lexer import Lexer
from parser import Parser
from semantic import SemanticAnalyzer
from codegen import LLVMCodeGenerator
from visualizer import ASTPrinter
from errors import CompilerError, LexerError, ParserError, SemanticError


def resolve_imports(source, base_dir, visited=None):
    if visited is None:
        visited = set()
    pattern = re.compile(r'^\s*import\s+(\w+)')
    lines = source.split('\n')
    result = []
    for line in lines:
        m = pattern.match(line)
        if m:
            mod_name = m.group(1)
            for ext in ['', '.cstar']:
                mod_path = os.path.normpath(os.path.join(base_dir, mod_name + ext))
                if os.path.isfile(mod_path):
                    break
            else:
                print(f"   -> Warning: module '{mod_name}' not found, skipped")
                continue
            abs_path = os.path.abspath(mod_path)
            if abs_path in visited:
                print(f"   -> Warning: circular import '{mod_name}' skipped")
                continue
            visited.add(abs_path)
            with open(abs_path) as f:
                mod_src = f.read()
            mod_src = resolve_imports(mod_src, os.path.dirname(abs_path), visited)
            result.append(mod_src)
        else:
            result.append(line)
    return '\n'.join(result)


def load_native_library(src_dir):
    import llvmlite.binding as llvm
    system = platform.system()
    if system == "Windows":
        lib_name = "lib_io.dll"
    elif system == "Linux":
        lib_name = "lib_io.so"
    elif system == "Darwin":
        lib_name = "lib_io.dylib"
    else:
        lib_name = "lib_io.so"

    lib_path = os.path.join(src_dir, lib_name)

    if not os.path.exists(lib_path) and system == "Linux":
        c_src = os.path.join(src_dir, "lib_io.c")
        if os.path.exists(c_src):
            print(f"   -> Compiling {lib_name} from lib_io.c...")
            ret = subprocess.run(
                ["gcc", "-O3", "-march=native", "-ffast-math", "-fPIC", "-shared",
                 "-o", lib_path, c_src, "-lm", "-lpthread"],
                capture_output=True, text=True
            )
            if ret.returncode != 0:
                print(f"   -> gcc failed: {ret.stderr}")
            else:
                print(f"   -> {lib_name} compiled")

    if os.path.exists(lib_path):
        llvm.load_library_permanently(lib_path)
        return True
    print(f"   -> Warning: {lib_name} not found, CSV i/o disabled")
    return False


def compile_pipeline(source, opt_level=3, show_ast=False):
    errors = []

    print("1. Lexing...")
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
    except LexerError as e:
        print(f"  [Lexer Error] {e}")
        sys.exit(1)

    print("2. Parsing...")
    parser = Parser(tokens)
    ast = parser.parse()
    if parser.errors:
        for e in parser.errors:
            print(f"  [Parser Error] {e}")
            errors.append(e)
        print("  Parsing failed.")
        sys.exit(1)
    print("  AST Generated Successfully")

    if show_ast:
        print("\n--- ABSTRACT SYNTAX TREE (AST) ---")
        printer = ASTPrinter()
        printer.print_node(ast)
        print("----------------------------------\n")

    print("3. Semantic Analysis...")
    try:
        analyzer = SemanticAnalyzer()
        analyzer.analyze(ast)
    except SemanticError as e:
        print(f"  [Semantic Error] {e}")
        sys.exit(1)

    if analyzer.errors.has_errors():
        for e in analyzer.errors.errors:
            print(f"  [Semantic] {e}")
        print("  Semantic analysis failed.")
        sys.exit(1)

    print("4. Generating LLVM IR...")
    try:
        codegen = LLVMCodeGenerator()
        codegen.generate(ast)
    except CompilerError as e:
        print(f"  [Codegen Error] {e}")
        sys.exit(1)

    print("  LLVM IR done.")
    return codegen


def main():
    parser_cli = argparse.ArgumentParser(
        description="C* (C-Asterisk) Compiler — compile .cstar files to native code via LLVM"
    )
    parser_cli.add_argument("file", help="Path to .cstar source file")
    parser_cli.add_argument("-O", type=int, default=3, choices=[0, 1, 2, 3],
                            help="Optimization level (default: 3)")
    parser_cli.add_argument("--ast", action="store_true",
                            help="Print the Abstract Syntax Tree")
    parser_cli.add_argument("--no-exec", action="store_true",
                            help="Skip JIT execution (compile + save only)")
    parser_cli.add_argument("--clean-cache", action="store_true",
                            help="Remove all cached bitcode files in obj/")
    args = parser_cli.parse_args()

    file_path = args.file

    if args.clean_cache:
        obj_dir = "obj"
        if os.path.isdir(obj_dir):
            for cf in os.listdir(obj_dir):
                if cf.endswith(".cached"):
                    os.remove(os.path.join(obj_dir, cf))
                    print(f"  Removed cache: {cf}")
        print("Cache cleaned.")

    try:
        with open(file_path, 'r') as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find the file '{file_path}'")
        sys.exit(1)

    print(f"--- Compiling {file_path} ---")
    source_code = resolve_imports(source_code, os.path.dirname(os.path.abspath(file_path)))

    codegen = compile_pipeline(source_code, show_ast=args.ast)

    if args.no_exec:
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        obj_path = os.path.join("obj", f"{base_name}.obj")
        os.makedirs("obj", exist_ok=True)
        codegen.save_object(obj_path)
        print(f"Object file saved to {obj_path}")
        print("Success! (Compilation only)")
        return

    # JIT Execution + Caching
    try:
        import llvmlite.binding as llvm

        src_dir = os.path.dirname(__file__)
        load_native_library(src_dir)

        os.makedirs("obj", exist_ok=True)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        source_hash = hashlib.sha256(source_code.encode()).hexdigest()[:16]
        cache_path = os.path.join("obj", f"{base_name}_{source_hash}.cached")

        if os.path.exists(cache_path):
            print(f"   -> Loading cached bitcode...")
            cache_mod = llvm.parse_assembly(open(cache_path).read())
            cache_mod.verify()
            print(f"   -> Cached bitcode verified, skipping JIT")
            codegen.module = cache_mod
        else:
            codegen.execute()
            bitcode = str(codegen.module)
            with open(cache_path, "w") as f:
                f.write(bitcode)
            for cf in os.listdir("obj"):
                if cf.startswith(base_name + "_") and cf.endswith(".cached") and cf != f"{base_name}_{source_hash}.cached":
                    os.remove(os.path.join("obj", cf))

        obj_path = os.path.join("obj", f"{base_name}.obj")
        codegen.save_object(obj_path)

    except Exception as e:
        print(f"[Runtime Error] {e}")
        sys.exit(1)

    print("Success! (Pipeline is completely wired up)")


if __name__ == "__main__":
    main()
