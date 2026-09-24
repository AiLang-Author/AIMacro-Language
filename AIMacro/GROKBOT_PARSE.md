# Grokbot: parse / transpile grind (branch `aimacro/class-body-parse-fixes`)

You are the **parse** Grokbot. A sibling instance is on **codegen**
(`grokasaurus2`). Do not take that branch. Do not start `--stage compile`.

Full overnight codegen contract: [GROKBOT_CODEGEN.md](GROKBOT_CODEGEN.md).
This file is **your** contract.

---

## Mission

Close **585/585 lib transpile** (`py2aim` + `aimacro.x` parse). One leftover
construct per commit. Tiny `.aim` first. After that, codegen is the other bot.

Start-of-shift numbers (py3.11 / 585, tip `a2591f0` + docs `65dd589`):

| Gate | Value |
|------|-------|
| lib transpile | **537/585** |
| in-scope | **380/395** (15 fail) |
| top token fail | `expected token 85 got 3` (7) |
| curated / matrix / fizzbuzz / Hash | 25/25, 62/62/62, 211054, 922 |

On py3.13 / 531, record **your** lib totals. Do not mix 531 and 585 in one line.

---

## Repo and branch

**Repo:** `https://github.com/AiLang-Author/AIMacro-Language` only.

```bash
git clone git@github.com:AiLang-Author/AIMacro-Language.git
cd AIMacro-Language
git fetch origin
git checkout aimacro/class-body-parse-fixes
git pull --ff-only origin aimacro/class-body-parse-fixes
```

You **may push** this branch:

```bash
git push origin aimacro/class-body-parse-fixes
```

You **may not**:

- push `main` / `master`
- push or commit on `grokasaurus2`
- push Ailang-Self-Hosting-
- force-push
- merge to main

Cherry-pick onto `main` is Grokasaurus’s job when they are back, not yours
unattended.

---

## Path (do not switch)

1. Isolate **one** remaining transpile fail (prefer in-scope files, then the
   largest token cluster).
2. Minimal `.aim` that fails the same parse error.
3. One patch: `py2aim.py` and/or `Librarys/AIMacro/` parser. Not CodeGen unless
   the file already parses and you are not on this shift.
4. Prove transpile OK. Run gates. If lib transpile rose, commit + push **this
   branch**.
5. Repeat. Hours OK. One construct per commit, same as before.

Do **not** start the compile tranche. The other bot owns that on `grokasaurus2`.

---

## Allowed

- `tools/py2aim.py`
- `Librarys/AIMacro/Library.AIMacroParser*.ailang`, Lexer, Core (parse holes)
- tiny `AIMacro_Tests/*.aim` repros
- scorecard notes in STATUS/CONFORMANCE after a real transpile rise

## Forbidden

- `Librarys/Compiler/`, Hash, Array, OOP, Arena, Plex, `ailang.x` sources
- MCP Hash/parsers
- new CodeGen libraries (that is `grokasaurus2`)
- rewriting CPython stdlib
- `--stage compile` as the goal of a commit

Host pattern is unchanged: rsync AIMacro into a Self-Hosting **worktree** that
has `ailang.x` + Hash 922; rebuild `aimacro.x`; never `git push` Self-Hosting.

---

## Gates before every push

| Gate | Must |
|------|------|
| curated | 25/25 |
| matrix | 62/62/62 |
| fizzbuzz ELF | 211054 |
| Hash | 922 |
| lib transpile | **must not drop**; should rise |
| SIGSEGV of aimacro.x | 0 |

---

## Remaining clusters (3.11 after `slice_suite_colon`)

`expected token 85 got 3` (7), timeout rc=124 (6), `85 got 2` (6),
`84 got 87` (6, class-body `}`), empty `__init__.py` (3). 48 transpile fails
total, 15 in-scope. Isolate **one**.

---

## Paste-back

```
parse grind <sha> on aimacro/class-body-parse-fixes
lib transpile: <ok>/585 (was <old>) in-scope <a>/395
curated 25/25 matrix 62/62/62 fizzbuzz 211054 Hash 922
construct: <name>
next leftover: <one error>
grokasaurus2: not touched
Self-Hosting: not pushed
```
