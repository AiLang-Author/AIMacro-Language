# AIMacro overnight compile — STATUS (2026-09-25)

## Applied steering
- CONFORMANCE ONLY (no optimize/profile)
- One construct per commit
- Branch grokasaurus2 only; Self-Hosting never pushed
- MCP publish only; never path-as-content

## Publishing now — CallIndirect / type-as-value batch
| Lib | md5 | notes |
|-----|-----|-------|
| cg2 | 9dc72a92 | getattr→callable mark; attr.add |
| cg4 | 9a168e06 | CallIndirect fallthrough; type-as-value MapBuiltin; class-as-value |
| oop | bc8af2d0 | Exception/BaseException/object → parent 0 |
| Extra | 65b7f137 | Complex/Callable/Range/MemoryView/Property/… stubs |

Repro: `AIMacro_Tests/compile_getattr_callable.aim`

Gates (host): curated **25/25**, matrix **84/84/84**, fizzbuzz **215153**, Hash **922**.

## Probe (py3.13 stdlib)
| Module | compile |
|--------|---------|
| heapq, colorsys, keyword, quopri, bisect | **ok** |
| **copy** | **ok** |
| statistics | `match` leftover (feature-tagged) |
| types | `func` / Ellipsis / globals (climb) |

## Ladder next
1. Finish MCP zlib publish + assemble verify
2. Climb types (func / Ellipsis / globals) and statistics
3. Widen compile probe

Self-Hosting: not pushed.
