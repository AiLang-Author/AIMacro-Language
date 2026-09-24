# AIMacro

Python-shaped surface syntax that **transpiles to AILang** and compiles to a native Linux ELF.

This is the **AOT `{ }` language**. It is not the 2025 `end`-keyword tree.

## Blocks are `{ }`. `end` is gone.

That is the language change.

| Era | Blocks | Compiler | This repo |
|-----|--------|----------|-----------|
| 2025 (`archive/end-syntax-2025`) | Python-ish indent + explicit `end` | Python `main.py` | old `main` |
| **2026 (this tree)** | **C-style `{ }`** | self-hosted `aimacro.x` → `ailang.x` | **`main`** |

`end` is not valid block syntax anymore. Indentation is not the grammar. Braces are.

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

Old (retired):

```aim
def factorial(n):
    if n <= 1:
        return 1
    end
    return n * factorial(n - 1)
end
```

`py2aim.py` is the indent-Python → `{ }` bridge. Do not port CPython by hand with `end`.

## Pipeline

```
.aim  →  ./aimacro.x  →  .ailang  →  ./ailang.x  →  native ELF
         (this repo)                 (AILang compiler)
```

- **AIMacro** lives here: https://github.com/AiLang-Author/AIMacro-Language
- **AILang compiler** (`ailang.x`, Hash, Array, OOP, …): https://github.com/AiLang-Author/Ailang-Self-Hosting-

AIMacro was parked inside the self-hosting compiler repo while AOT work ran. It is back in this repo. Grokbot / class-body grind: work **here**, not in `Ailang-Self-Hosting-`.

## Build

Needs `ailang.x` on `PATH` (or in this directory). From the compiler repo:

```bash
# in Ailang-Self-Hosting-
./ailang.x   # already built, or rebuild per that repo

# in AIMacro-Language (this repo)
cp /path/to/Ailang-Self-Hosting-/ailang.x .
./ailang.x aimacro_cli.ailang aimacro
mv -f aimacro aimacro.x
```

`ailang.x` inlines `Librarys/AIMacro/` at compile time. Rebuild `aimacro.x` after parser/codegen edits.

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

## Layout

```
Librarys/AIMacro/          lexer, parser, codegen, runtime builtins
aimacro_cli.ailang         CLI transpiler source
aimacro_console.ailang     interactive console
AIMacro/                   spec, status, scripts
AIMacro_Tests/             62 .aim matrix tests
tests/python/curated/      25 CPython gold files
tools/py2aim.py            indent Python → { } .aim
tools/aimacro_cpython_runner.py
```

Keep `Librarys/AIMacro/` at that path. `LibraryImport.AIMacro.*` resolves there.

## Docs

| File | What |
|------|------|
| [AIMacro/SPECIFICATION.md](AIMacro/SPECIFICATION.md) | language contract (`{ }` is the syntax rule) |
| [AIMacro/ARCHITECTURE.md](AIMacro/ARCHITECTURE.md) | pipeline |
| [AIMacro/CONFORMANCE.md](AIMacro/CONFORMANCE.md) | CPython-lite scorecard |
| [AIMacro/STATUS.md](AIMacro/STATUS.md) | living gates |
| [AIMacro/PYTHON_TESTS.md](AIMacro/PYTHON_TESTS.md) | runner |
| [AIMacro/GROKBOT_CODEGEN.md](AIMacro/GROKBOT_CODEGEN.md) | unattended codegen shift (`grokasaurus2`) |

## History in this GitHub repo

- **`archive/end-syntax-2025`** — last `end` / Python-compiler snapshot (`493cfdc8`, 2025-12-23)
- **`main`** — AOT `{ }` tree imported from `Ailang-Self-Hosting-` `aimacro/class-body-parse-fixes` @ `26b4560d`

## License

Sean Collins Software License (SCSL v1.0). Copyright (c) 2025–2026 Sean Collins, 2 Paws Machine and Engineering.
