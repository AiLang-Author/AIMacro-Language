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
| compile_getattr | `AIMacro_Tests/compile_getattr.aim` → `None`/`None` | Gen_MapBuiltin getattr→AIMacro.GetAttr (Extra); pad default |
| compile_ctor_attr | `AIMacro_Tests/compile_ctor_attr.aim` → compiles | Flatten class ctor + dict values before Hash.Set |

Gates (host): curated **25/25**, matrix **78/78/78**, fizzbuzz **215153**, Hash **922**.

## Probe (py3.13 stdlib)
| Module | compile |
|--------|---------|
| heapq, colorsys, keyword, quopri, bisect | **ok** |
| copy | getattr OK; next **Unknown function: id** |
| statistics | was Unexpected token → now **duplicate pdf/cdf** (parse OK) |
| types | Unexpected token / Ellipsis / globals |

## Ladder
1–8. ~~map…getattr~~ (getattr on tip e6c8d79)
9. ~~ctor_attr~~ (local green; publish cg2+cg3 zlib)
10. Next: statistics duplicate method names; copy `id`; types Ellipsis/globals.

Self-Hosting: not pushed.
