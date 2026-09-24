# Grokbot overnight: AIMacro codegen (branch `grokasaurus2`)

Unattended contract. Read this whole file before touching a file. If a rule
here conflicts with a habit from the parse grind, **this file wins**.

You are **Grokbot**. You are not Grokasaurus. You push **only**
`grokasaurus2` on **AIMacro-Language**. You do not merge `main`. You do not
push Self-Hosting. You do not MCP.

---

## Mission

Make **transpiled** CPython stdlib **compile** with `ailang.x`.

Bar (already written into OBJECTIVES / README):

1. Transpile all 585 stdlib `.py` (parse grind; keep it from going backwards)
2. **This shift: compile all 585** — `ailang.x` must accept the generated `.ailang`
3. Run vs CPython is later. Do not switch to run until compile is moving.

A 2026-09-24 probe of **26 transpile-ok** modules (`colorsys`, `keyword`,
`heapq`, `enum`, `pathlib`, `zipfile`, …) was **0/26 compile**. Split:

| n | What | Example |
|---|------|---------|
| 20 | `ailang.x` **SIGSEGV** (rc=-11 / 139) after a parse error in the *generated* `.ailang` | `Expected ')' after arguments` then crash |
| 6 | clean compile fail (rc=1) | `Variable not found: ONE_THIRD` (`colorsys`); `Unknown function: frozenset` (`keyword`) |

Transpile-ok does **not** mean the `.ailang` is legal AILang. Your job is the
**emitter and AIMacro runtime**, not the AILang compiler.

---

## Repos (do not confuse them)

| Repo | GitHub | Role |
|------|--------|------|
| **AIMacro-Language** | `https://github.com/AiLang-Author/AIMacro-Language` | **Canonical. You work here.** Parser, codegen, runtime, `py2aim`, tests, this file. |
| **Ailang-Self-Hosting-** | `https://github.com/AiLang-Author/Ailang-Self-Hosting-` | **Compile host only.** Provides `ailang.x`, Hash, Array, OOP, Arena, Plex. **Read-only.** |

Pull AIMacro at tip of `main` (must include `a2591f0` slice_suite_colon or later).
Create and push:

```bash
git clone git@github.com:AiLang-Author/AIMacro-Language.git
cd AIMacro-Language
git checkout main
git pull --ff-only origin main
git checkout -b grokasaurus2
git push -u origin grokasaurus2
```

Branch name is exactly **`grokasaurus2`**. Not `main`, not `master`, not the
parse grind `aimacro/class-body-parse-fixes`.

---

## Duplicate-file cleanup (do this first, once)

Self-Hosting still contains a **stale extract** of AIMacro. Those copies are
**behind** this repo (ParserCore, py2aim, CodeGen all diverge). They are not
yours to “fix in place.”

| Path in Self-Hosting | What to do |
|----------------------|------------|
| `Librarys/AIMacro/` | **Do not edit. Do not commit. Do not push.** Stale mirror. |
| `AIMacro/`, `AIMacro_Tests/` | Ignore. Canonical copies are in AIMacro-Language. |
| `aimacro_cli.ailang`, `aimacro_console.ailang` | Ignore. |
| `tools/py2aim.py`, `tools/aimacro_cpython_runner.py` | **Stale.** Self-Hosting py2aim is ~7.6 KB; this repo is ~16 KB. |
| `Librarys/Library.Hash.ailang` | Compiler runtime. **Do not MCP. Do not shrink. 922 lines.** |
| `Librarys/Compiler/`, lexer/parser of AILang | **Forbidden.** |

**Host worktree pattern** (required):

```bash
# compiler host with ailang.x + Hash 922 — never git-commit AIMacro here
HOST=/tmp/aimacro-codegen-host
# clone or copy Self-Hosting once, build/copy ailang.x into HOST
rsync -a --delete /path/to/AIMacro-Language/Librarys/AIMacro/ $HOST/Librarys/AIMacro/
cp /path/to/AIMacro-Language/aimacro_cli.ailang $HOST/
cp /path/to/AIMacro-Language/tools/py2aim.py $HOST/tools/
cp /path/to/AIMacro-Language/tools/aimacro_cpython_runner.py $HOST/tools/
cd $HOST
./ailang.x aimacro_cli.ailang aimacro && mv -f aimacro aimacro.x
```

After every AIMacro edit: rsync `Librarys/AIMacro/` + `aimacro_cli.ailang` into
`$HOST`, rebuild `aimacro.x`. If `$HOST` is a git checkout of Self-Hosting,
`git checkout -- Librarys/AIMacro` when you are done so you never accidentally
commit it. **Never `git push` Self-Hosting.**

Do **not** delete the stale trees from Self-Hosting in this shift (include-path
and history). Cleanup = **stop using them** and **never commit them**.

---

## What you MAY change (AIMacro-Language only)

- `Librarys/AIMacro/*.ailang` — lexer, parser, **codegen**, runtime builtins
- **New** codegen/runtime libraries in `Librarys/AIMacro/` (example:
  `Library.AIMacroCodeGen5.ailang`, `Library.AIMacroCodeGenBuiltin.ailang`).
  Wire them with `LibraryImport.AIMacro.*` from `aimacro_cli.ailang` and any
  CodeGen file that calls them. Keep the `Librarys/AIMacro/` path.
- `aimacro_cli.ailang` — imports only, plus CLI if a new lib must load
- `tools/py2aim.py` — only if a brace-bridge bug emits `.aim` that cannot
  codegen (do not turn this into a parse-grind)
- `AIMacro_Tests/*.aim` — tiny repros for the construct you just fixed
- `AIMacro/STATUS.md` / `CONFORMANCE.md` — scorecard after a real compile move

Every feature = emit (and runtime if the emit calls `AIMacro.*`) + a tiny `.aim`
that **compiles** (and runs if it is a values test).

---

## What you MUST NOT change

**AILang compiler (absolute):**

- `Librarys/Compiler/`
- `Librarys/Library.Hash.ailang` (922 lines, insertion-order)
- Array / OOP / Arena / Plex / JSON / StringUtils **in Self-Hosting**
- `ailang.x` sources, ELF layout, parser of `.ailang`

If generated `.ailang` SIGSEGVs `ailang.x`, the **emit is illegal**. Fix the
emitter so it produces legal AILang (or a simpler legal form). Do **not**
“harden” the compiler. Do not MCP Hash or parsers.

**Also forbidden:**

- `git push` to `main` / `master` on either repo
- `git push` Self-Hosting any branch
- Force-push
- Merge `grokasaurus2` into `main`
- Rewriting CPython stdlib files
- Drive-by refactors, renaming, “cleanup” of CodeGen1–4 unrelated to the
  current compile fail
- VM / bytecode work
- Packaging, pip, venv

---

## Hard gates (must stay green every push)

On the **host** after each construct, before `git push`:

| Gate | Command / check | Must |
|------|-----------------|------|
| curated | `python3 tools/aimacro_cpython_runner.py --corpus curated` | **25/25** |
| matrix | `./AIMacro/scripts/run_matrix.sh` | **62/62/62** |
| fizzbuzz ELF | `./ailang.x AIMacro_Tests/fizzbuzz.ailang /tmp/fizz.x && stat -c %s` | **211054** |
| Hash | `wc -l Librarys/Library.Hash.ailang` in the **host** | **922** |
| lib **transpile** | `--corpus lib --stage transpile` | must **not drop** vs start-of-shift (3.11: **537/585**, in-scope **380/395** at `b8251df` / `a2591f0`; 3.13 numbers differ — record yours) |
| lib **compile** | `--corpus lib --stage compile` (or a growing probe of transpile-ok files) | **must rise** vs previous push on this branch |
| SIGSEGV of **aimacro.x** during transpile | | **0** |

`ailang.x` SIGSEGV on a **bad .ailang** is a **codegen bug**, not a “compiler
SIGSEGV gate fail.” Count it as a compile-fail. Fix emit. Do not “pass” by
skipping the file.

The runner used to drop `ailang.x` **stdout** on compile fail (errors look
empty). Current `tools/aimacro_cpython_runner.py` keeps stdout. Use **this
repo’s** runner, not Self-Hosting’s.

---

## Loop (hours; one construct per commit)

```
while compile_ok is rising OR you still have a minimal repro:
    1. Pick ONE compile-fail from files that already transpile.
       Prefer: (a) rc=1 with a named missing symbol
               (b) smallest .py
               (c) SIGSEGV with a short parse error on stdout
    2. Reduce to a tiny .aim that fails the same way.
       Examples already known:
         - module-level ONE_THIRD used inside a def  → Variable not found
         - frozenset(kwlist).__contains__            → Unknown function: frozenset
         - illegal call/paren emit                   → Expected ')' then SIGSEGV
    3. Capture FULL `ailang.x` stdout+stderr (not just stderr).
    4. Fix emit and/or AIMacro.* runtime. New Library.AIMacroCodeGen*.ailang is OK.
    5. rsync + rebuild aimacro.x. Repro must compile (and run if it is a value test).
    6. Run gates. If curated/matrix/fizzbuzz/transpile-lib regress: REVERT, do not push.
    7. git commit on grokasaurus2 (one construct, message like the parse grind).
    8. git push origin grokasaurus2
    9. Next leftover. Do not stop after one if the machine is still up.
```

Commit message shape:

```
feat(aimacro): compile_<construct>  <one-line repro>

<why the .ailang was illegal / which AIMacro.* you added>
```

Do not batch five unrelated builtins in one commit unless they are the same
`Gen_MapBuiltin` hole and one smoke covers them.

---

## How to add a builtin (typical rc=1 `Unknown function`)

1. Implement `Function.AIMacro.YourName` in `Library.AIMacro.ailang` (or a new
   `Library.AIMacroCodeGenBuiltin.ailang` imported by CodeGen4 / cli).
2. Map it in `Gen_MapBuiltin` (`Library.AIMacroCodeGen4.ailang`) so
   `frozenset(...)` emits `AIMacro.FrozenSet(...)` not a raw `frozenset(...)`.
3. Tiny `.aim`: `print(frozenset([1,2]))` or whatever the stdlib line needs.
4. If you `ReturnValue(name)` from `Gen_MapBuiltin` for an unknown ident, the
   compiler looks for a Function of that name and dies. **Never leave Python
   builtins unmapped** if they appear in the compile-fail set.

## How to fix module-level constants (typical `Variable not found: ONE_THIRD`)

`colorsys.py` does `ONE_THIRD = 1.0/3.0` at file scope, then uses it inside
`hls_to_rgb`. Emit so the name exists **before** the function body runs
(hoist file-scope assigns, or emit a real global the function can see). Do not
inline one constant and leave `ONE_SIXTH` broken. Prove with a 10-line `.aim`.

## How to treat SIGSEGV of `ailang.x`

1. Keep the generated `.ailang`.
2. Note the last `PARSE ERROR` / `COMPILE ERROR` line on stdout.
3. That construct’s emit is wrong (extra `{`, missing `)`, illegal call).
4. Change CodeGen so the same `.aim` produces legal AILang.
5. If you cannot emit the Python faithfully yet, emit a **legal subset** that
   still compiles (stub that returns None / empty list) **only** after a comment
   in the commit says it is a stub. Prefer a real implementation.

---

## Compile measurement

```bash
# growing compile scorecard (host cwd has aimacro.x + this repo's runner + py2aim)
python3 tools/aimacro_cpython_runner.py --corpus lib --stage compile \
  --cpython "$CPYTHON_LIB" \
  --timeout 20 \
  --output-json /tmp/aimacro_lib_compile_${CONSTRUCT}.json
```

`$CPYTHON_LIB` is `sysconfig.get_path("stdlib")` or the 3.11 tree
`/home/bob/tools/oss-cad-suite/lib/python3.11` (585 files) if present.
On the 3.13 VM, record **your** total (was 531). Do not mix the two in one
scorecard line.

If full `--stage compile` on 585 is too slow/noisy at first: compile the
**transpile-ok** set (or the 26-file probe) and publish `compile_ok/N` every
push. Full 585 compile is the bar; a rising probe is the overnight metric.

---

## MCP / Hash

Do not MCP `Library.Hash`, ParserCore, ParserOOP, or Compiler. A previous MCP
wipe replaced Hash with a stub and broke curated dict order. If Hash is not
922 lines in the host, restore it from Self-Hosting git. Never “fix” Hash.

---

## Stop conditions (then stop pushing and leave a STATUS note)

Stop a construct and write `AIMacro/STATUS.md` if:

- curated drops below 25/25
- matrix drops below 62/62/62
- fizzbuzz size changes
- lib **transpile** drops
- you are about to edit compiler sources to silence a SIGSEGV

Otherwise keep looping until the machine stops or compile_ok saturates.

---

## Paste-back (end of shift, or every few hours)

One block:

```
grokasaurus2 <sha>
compile probe/lib: <ok>/<n> (was <old>)
transpile lib: <ok>/<total> in-scope <a>/<b>
curated 25/25 matrix 62/62/62 fizzbuzz 211054 Hash 922
constructs this shift: <list>
next leftover: <one compile error>
Self-Hosting: not pushed
```
