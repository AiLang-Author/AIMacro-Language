# AIMacro Project Objectives

## Mission

Deliver a **production-usable Python surface** on top of AILang (`{ }` blocks,
not indentation). The CPython stdlib corpus (585 `.py` on 3.11 after excludes)
must **all transpile and all compile**. Tagged files (`async`, `yield`, `@`,
`match`) are still in the 585 — skip tags are triage, not a pass. After that
corpus compiles, chase run/codegen holes until the modules actually work.
VM (JSVM-style REPL) comes after AOT stays green. See [PYTHON_GAP.md](PYTHON_GAP.md).

---

## Primary objectives

### O1 — Document and gate the pipeline

**Goal:** Every contributor (human or agent) can transpile, compile, and run tests
without guessing.

**Deliverables:**
- Architecture, spec, test matrix (this directory)
- `scripts/run_transpile_all.sh` and `scripts/run_pipeline.sh`
- Living `STATUS.md` scorecard

**Success:** One command reports transpile/compile/run status for all tests.

---

### O2 — Close the CPython stdlib corpus (transpile, then compile)

**Goal:** All 585 stdlib `.py` files transpile (`py2aim` + `aimacro.x`) and then
compile (`ailang.x`). Not a 95th-percentile subset. Not “in-scope only.”

**Tranche A (now):** 585/585 transpile. Remaining ~65 parse holes (token mismatches,
timeouts, empty `__init__` handling).

**Tranche B (next):** `--stage compile` on that corpus. Probe 2026-09-24: **0/26**
transpile-ok modules compiled (20 `ailang.x` SIGSEGV, 6 `Variable not found` /
`Unknown function`). That is the next scorecard.

**Tranche C:** run vs CPython where the module is a script-shaped surface; shims
for `os`/`json`/`sys` already exist and must keep growing.

**Success:** `python3 tools/aimacro_cpython_runner.py --corpus lib --stage transpile`
is 585/585, then `--stage compile` is 585/585. Matrix 62/62/62 and curated 25/25
stay green the whole time.

---

### O3 — Runtime library completeness

**Goal:** `Library.AIMacro.ailang` implements every builtin the codegen references.

**Work:**
- Audit `Gen_MapBuiltin` + `Gen_CallExpr` specials vs `AIMacro.*` functions
- Fill missing shims (file I/O, module helpers)
- Fix `Smart*` dispatch edge cases (len on unknown types, etc.)

**Success:** No codegen reference to undefined `AIMacro.*` or `Types.*` symbol.

---

### O4 — AIMacroVM (post-transpiler)

**Goal:** Dual execution like JS stack: compile to bytecode OR transpile to AILang.

**Components:**
1. `Library.AIMacroCompiler.ailang` — AST → bytecode + const pool
2. `Library.AIMacroRuntime.ailang` — value model, coercion
3. `Library.AIMacroVM.ailang` — interpreter loop
4. `Library.AIMacroVM.Builtins.ailang` — builtin dispatch table
5. Console VM mode in `aimacro_console.ailang`

**Success:** REPL evaluates `(1+2)*3` and `print("hello")` without invoking `ailang.x`.

---

## Non-objectives (this project phase)

- Packaging / pip / venv / a CPython `Lib/test` unittest runner
- Non-Linux AOT targets (BSD/Windows syscall backends are a separate OS project)
- Replacing the AILang compiler
- Shipping a VM before AOT stdlib compile is green

`async` / `yield` / `@` / `match` / `lambda` are **not** skip-forever. They must
parse and AOT-compile with the rest of the 585. Runtime for those can lag;
dropping the file is not done.

---

## Milestones

| ID | Milestone | Target | Exit criteria |
|----|-----------|--------|---------------|
| M0 | Project bootstrap | Week 0 | Docs + branch + scripts (this commit) |
| M1 | Test audit | Week 1 | `STATUS.md` filled for all 42 tests |
| M2 | Tier A green | Week 2–3 | P0 matrix ≥90% run pass |
| M3 | Tier B green | Week 4–6 | dict + OOP + isinstance E2E |
| M4 | Tier C features | Week 7–9 | open + import + one comprehension or f-string |
| M5 | VM spike | Week 10–11 | 10-opcode VM runs arithmetic + print |
| M6 | VM P0 parity | Week 12+ | VM passes Tier A matrix |

---

## Workstreams

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  WS1: Parser    │     │  WS2: Codegen   │     │  WS3: Runtime    │
│  Lexer/Parser   │────▶│  CodeGen1-4     │────▶│  Library.AIMacro │
│  OOP extensions │     │  OOP/Dict       │     │  AIMacroDict     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │  WS4: Test matrix + CI  │
                    │  AIMacro_Tests/*.aim    │
                    │  scripts + STATUS.md    │
                    └─────────────────────────┘
                                 │
                                 ▼ (after M4)
                    ┌─────────────────────────┐
                    │  WS5: VM                │
                    │  Compiler + VM + REPL   │
                    └─────────────────────────┘
```

---

## Agent / contributor rules

1. **Every feature** = parser node (if needed) + codegen + runtime + `.aim` test
2. **Never** break AOT path while building VM — feature-flag VM code
3. Update `STATUS.md` when fixing a test tier
4. Prefer extending `Gen_MapBuiltin` over ad-hoc call hacks
5. Reference `Library.JSVM.ailang` for VM loop patterns (dispatch, frames, builtins)

---

## Key files (quick reference)

| Task | Primary files |
|------|---------------|
| New syntax | `AIMacroParserCore.ailang`, `AIMacroLexer.ailang` |
| New statement codegen | `AIMacroCodeGen2.ailang` |
| New expression/builtin | `AIMacroCodeGen4.ailang` |
| New builtin runtime | `Library.AIMacro.ailang` |
| OOP | `AIMacroParserOOP.ailang`, `AIMacroCodeGenOOP.ailang` |
| Dicts | `AIMacroCodeGenDict.ailang`, `AIMacroDict.ailang` |
| CLI | `aimacro_cli.ailang` |
| Tests | `AIMacro_Tests/*.aim` |