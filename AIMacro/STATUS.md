# AIMacro overnight compile — STATUS (2026-09-25)

## Applied steering
- CONFORMANCE ONLY (no optimize/profile)
- One construct per commit
- Branch grokasaurus2 only; Self-Hosting never pushed
- MCP publish only; never path-as-content

## Local (box) — green
| Construct | Repro | Notes |
|-----------|-------|-------|
| compile_map_builtin | `AIMacro_Tests/compile_map_builtin.aim` → `3` | Gen_MapBuiltin map→AIMacro.Map; CallIndirect |
| compile_iter_builtin | `AIMacro_Tests/compile_iter_builtin.aim` → `3`/`2` | iter→AIMacro.Iter; IDENT builtins AddressOf |
| compile_next_builtin | `AIMacro_Tests/compile_next_builtin.aim` → `10`/`20` | next→AIMacro.Next; `it.__next__` → CallIndirect |
| compile_h_append_bound | `AIMacro_Tests/compile_h_append_bound.aim` → `2` | `h_append=h.append` → AddressOf(SmartPush)+bound self |
| compile_copier_dispatch | `AIMacro_Tests/compile_copier_dispatch.aim` → `7` | `dispatch.get` → MarkCallable+CallIndirect; module dict marks; type()→TypeName |
| compile_return_listcomp_method | `AIMacro_Tests/compile_return_listcomp_method.aim` → `[1, 2, 3]` | OOPGen_FlattenExpr LIST_COMP → Gen_FlattenExpr (method return hoist) |
| compile_issubclass | `AIMacro_Tests/compile_issubclass.aim` → `True`/`False` | Gen_MapBuiltin issubclass→AIMacro.IsSubclass (Extra); ptr-eq |

Gates (host): curated **25/25**, matrix **76/76/76**, fizzbuzz **215153**, Hash **922**.

## Probe (py3.13 stdlib)
| Module | compile |
|--------|---------|
| heapq, colorsys, keyword, quopri, bisect | **ok** |
| copy | was **issubclass** → now **getattr** (rc=1) |
| statistics | Unexpected token (rc=139) |
| types | Unexpected token then SIGSEGV |

## Ladder
1. ~~map~~ 2. ~~iter~~ 3. ~~next~~ 4. ~~h_append_bound~~ 5. ~~copier_dispatch~~ 6. ~~return_listcomp_method~~ 7. ~~issubclass~~
8. Next leftover: `getattr` (copy.py rc=1) or statistics/types Unexpected token.

Self-Hosting: not pushed.
