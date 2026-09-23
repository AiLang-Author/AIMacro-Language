# AIMacro

AIMacro is a Python-like language that transpiles to AILang and then compiles to a native Linux executable.

The syntax is intentionally familiar to Python programmers, but blocks use `{ }` instead of indentation and `end`.

This is the current AOT language for this repo. The older 2025 syntax with `end` is kept only in the archived branch.

## Block syntax

AIMacro uses braces for blocks:

```aim
def factorial(n) {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

def main() {
    print(factorial(10))
}
```

This is the main difference from the old 2025 version:

```aim
def factorial(n):
    if n <= 1:
        return 1
    end
    return n * factorial(n - 1)
end
```

The old `end`-based syntax is retired. Indentation is not part of the grammar; braces are.

## Pipeline

```text
.aim  ->  ./aimacro.x  ->  .ailang  ->  ./ailang.x  ->  native ELF
```

- `aimacro.x` is the transpiler in this repo.
- `ailang.x` is the AILang compiler used for the final build.
- The output is a native Linux ELF binary.

## Build

This repo expects `ailang.x` to be available on `PATH` (or in the repo directory).

From the AILang compiler repo:

```bash
./ailang.x
```

Then in this repo:

```bash
cp /path/to/Ailang-Self-Hosting-/ailang.x .
./ailang.x aimacro_cli.ailang aimacro
mv -f aimacro aimacro.x
```

After that, you can transpile and run a program:

```bash
./aimacro.x AIMacro_Tests/fizzbuzz.aim /tmp/fizzbuzz.ailang
./ailang.x /tmp/fizzbuzz.ailang /tmp/fizzbuzz.x
/tmp/fizzbuzz.x
```

## Current status

The project is in active development. The current tree is the brace-based AOT implementation.

The repo includes:

- `Librarys/AIMacro/` — lexer, parser, code generation, runtime builtins
- `aimacro_cli.ailang` — command-line transpiler source
- `aimacro_console.ailang` — interactive console
- `AIMacro/` — specs, status, and scripts
- `AIMacro_Tests/` — test suite
- `tests/python/curated/` — curated Python compatibility checks
- `tools/py2aim.py` — helper for converting indent-based Python into brace-based `.aim` code

## Documentation

| File | Purpose |
|------|---------|
| [AIMacro/SPECIFICATION.md](AIMacro/SPECIFICATION.md) | Language contract and syntax rules |
| [AIMacro/ARCHITECTURE.md](AIMacro/ARCHITECTURE.md) | Execution pipeline and design |
| [AIMacro/CONFORMANCE.md](AIMacro/CONFORMANCE.md) | Compatibility and scorecard |
| [AIMacro/STATUS.md](AIMacro/STATUS.md) | Current build and test status |
| [AIMacro/PYTHON_TESTS.md](AIMacro/PYTHON_TESTS.md) | Test runner and coverage notes |

## History in this repository

- `archive/end-syntax-2025` — the older `end`-based snapshot
- `main` — the current brace-based implementation

## License

Sean Collins Software License (SCSL v1.0). Copyright (c) 2025–2026 Sean Collins, 2 Paws Machine and Engineering.
