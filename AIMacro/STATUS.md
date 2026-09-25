# AIMacro overnight compile — STATUS (2026-09-25)

## Applied steering
- CONFORMANCE ONLY (no optimize/profile)
- One construct per commit
- Branch grokasaurus2 only; Self-Hosting never pushed
- MCP publish only; never path-as-content

## Local (box) — green
| Construct | Repro | Notes |
|-----------|-------|-------|
| compile_ctor_attr | `compile_ctor_attr.aim` → compiles | Flatten class ctor + dict values before Hash.Set |
| compile_id_builtin | `compile_id_builtin.aim` → ptr / True | MapBuiltin id→AIMacro.Id |
| compile_nested_def_dup | `compile_nested_def_dup.aim` → binds | Nested def → `__nest_N_name` + AddressOf bind |
| compile_tuple_builtin | `compile_tuple_builtin.aim` | MapBuiltin tuple→AIMacro.Tuple; TypeID.LIST |
| compile_hasattr_builtin | → False | MapBuiltin hasattr→AIMacro.HasAttr stub |
| compile_setattr_builtin | → 1 | MapBuiltin setattr→AIMacro.SetAttr stub |

Gates (host): curated **25/25**, matrix **83/83/83**, fizzbuzz **215153**, Hash **922**.

## Probe (py3.13 stdlib)
| Module | compile |
|--------|---------|
| heapq, colorsys, keyword, quopri, bisect | **ok** |
| copy | id/tuple/hasattr/setattr OK; next **Unknown function: func** (CallIndirect) |
| statistics | duplicate pdf/cdf **fixed** (`__nest_*`); next **types_add** CallIndirect |
| types | **Unknown function: meta** (CallIndirect / metaclass) |

## Ladder
~~ctor_attr~~ published (cg2 4805dc38 / cg3 1eb1a27b assemble OK).
Next publish: id+nested+tuple/hasattr/setattr (Extra+cg2+cg4).
Next leftover: copy `func` / statistics `types_add` / types `meta` CallIndirect.

Self-Hosting: not pushed.
analyzer.x spot-check statistics: 0 errors, 2656 warnings.
