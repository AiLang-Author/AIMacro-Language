# AIMacro overnight COMPILE — STATUS (2026-09-25)

## Applied steering
- CONFORMANCE ONLY (no optimize/profile)
- One construct per commit
- Branch grokasaurus2 only; Self-Hosting never pushed
- MCP publish only; never path-as-content

## Published (remote)
| Item | Notes |
|------|-------|
| compile_ctor_attr | cg2 `4805dc38` 87p / cg3 `1eb1a27b` 55p assemble OK |
| compile_id_nested + builtins | tip family through `266b3f0` Extra Id/HasAttr/SetAttr; cg2 `fa3d4434` 88p; cg4 `10f4b073` 68p assemble OK |

## Local (box) — green; zlib NOT yet published
Local md5: cg2 `9dc72a92…` cg4 `9a168e06…` oop `bc8af2d0…` Extra `65b7f137…`

| Construct | Notes |
|-----------|-------|
| getattr→callable | CodeGen2; test `compile_getattr_callable.aim` |
| CallIndirect fallthrough | CodeGen4 unknown non-builtin → CallIndirect |
| type-as-value MapBuiltin | list/dict/set/int/float/bool/str/complex/callable/range/… |
| Exception parent→0 | CodeGenOOP |
| class-as-value | IDENT class → string |
| Extra stubs | Complex/Callable/MemoryView/Property/… |

Gates: curated **25/25**, matrix **84/84/84**, fizzbuzz **215153**, Hash **922**.

## Probe (py3.13)
| Module | compile |
|--------|---------|
| heapq/colorsys/keyword/quopri/bisect | **ok** |
| **copy** | **ok** |
| statistics | `match` (feature-tagged) |
| types | `func` (feature-tagged) |
| in-scope probe | **4/4** |

## Next
1. MCP zlib publish CallIndirect/type-value batch (cg2+cg4+oop+Extra+manifest)
2. types `func`; statistics `match` skip/unsupported
3. Long-loop prefer climb

Self-Hosting: not pushed.
