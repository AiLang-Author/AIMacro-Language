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

## Bar

Every CPython stdlib `.py` in the corpus must **transpile and compile**. On this box that is **585** files (Python 3.11.6, after dropping `test/`, `tkinter/`, …). Skipping tagged files (`async`, `yield`, `@`, `match`) is a triage label, not a done state. Those files still have to parse and AOT-compile.

Tranches, in order:

1. **Transpile all 585** — `py2aim` + `aimacro.x` parse/codegen emit `.ailang`
2. **Compile all 585** — `ailang.x` AOT on that `.ailang`
3. **Run** — execute vs CPython where that is meaningful

95th-percentile was the old ceiling. It is not the stop. AOT stays production; VM is later.

## Gates (2026-09-24, py3.11 / 585, tip `a1eb820`)

| Gate | Result |
|------|--------|
| curated (`tests/python/curated`, stdout vs CPython) | **25/25** |
| internal matrix (`AIMacro_Tests/*.aim`) | **62/62/62** transpile/compile/run |
| CPython stdlib lib **transpile** | **537/585** (in-scope **380/395**) at `a2591f0` |
| CPython stdlib lib **compile** | probe **0/26** on transpile-ok modules (20 SIGSEGV, 6 codegen) |
| SIGSEGV | **0** |
| fizzbuzz ELF | **211054** |

## Documentation

| File | Purpose |
|------|---------|
| [AIMacro/SPECIFICATION.md](AIMacro/SPECIFICATION.md) | Language contract and syntax rules |
| [AIMacro/ARCHITECTURE.md](AIMacro/ARCHITECTURE.md) | Execution pipeline and design |
| [AIMacro/CONFORMANCE.md](AIMacro/CONFORMANCE.md) | Compatibility and scorecard |
| [AIMacro/STATUS.md](AIMacro/STATUS.md) | Current build and test status |
| [AIMacro/PYTHON_TESTS.md](AIMacro/PYTHON_TESTS.md) | Test runner and coverage notes |
| [AIMacro/GROKBOT_CODEGEN.md](AIMacro/GROKBOT_CODEGEN.md) | Unattended codegen shift (`grokasaurus2`) |
| [AIMacro/GROKBOT_PARSE.md](AIMacro/GROKBOT_PARSE.md) | Parse/transpile grind (`aimacro/class-body-parse-fixes`) |

## History in this repository

- `archive/end-syntax-2025` — the older `end`-based snapshot
- `main` — the current brace-based implementation

## License

Sean Collins Software License (SCSL v1.0). Copyright (c) 2025–2026 Sean Collins, 2 Paws Machine and Engineering.
