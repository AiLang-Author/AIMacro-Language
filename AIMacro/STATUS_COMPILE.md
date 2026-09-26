# AIMacro overnight compile — STATUS (2026-09-25)

## Widen
**57/76** (was 56). `typing` newly OK.

## Tip constructs (this stretch)
| Construct | notes |
|-----------|-------|
| nested tuple-unpack assign | py2aim `desugar_tuple_unpack` via `_for_unpack_assigns` (cleared `\\x04`) |
| nested class freevars | py2aim `_aim_ncells` module dict (typing `superclass_name`) |
| AILang kw escape Tuple/Add | CodeGen1 `Gen_EmitIdent`/`Lhs` → `PyMod.Tuple`/`Add` (ast PARSE cleared) |
| rt listreverse | micros .000-.034 → md5 c1532629 |
| cg2 markslice | micros .000-.039 → md5 5c3da1fb |

## Tip md5s (host / tip_manifest)
| artifact | md5 |
|----------|-----|
| CodeGen1 | `793bdc4ce4798adc4660f10a042350a4` |
| CodeGen2 | `5c3da1fbb75adcbc8b804de9d2655124` |
| AIMacro.ailang (rt) | `c15326296d8dbdc13a246b0dc531a1c1` |
| tools/py2aim.py | `eac63c5166ac4bbb47369bea173bd40a` |
| Hash | 922 |

## Leftovers (widen fails)
ast: PARSE cleared; `Variable not found: PyCF_ONLY_AST` (`from _ast import *` shim)
others: pathlib/zipfile/tokenize/inspect/… (ailang); dis/turtle/configparser/concurrent (aimacro/py2aim)

## Gates
Host tip Libraries assembled; `aimacro.x` rebuilt OK (~490796).
Origin: tip micros for rt/cg2/cg1/py2aim; Library tip_direct rt/cg2 still pending inbox.

Self-Hosting: not pushed. No compiler edits. Conformance only.
