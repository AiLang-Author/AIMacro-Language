# AIMacro overnight compile - STATUS (2026-09-25)

## Applied steering
- CONFORMANCE ONLY (no optimize/profile)
- One construct per commit
- Branch grokasaurus2 only; Self-Hosting never pushed
- MCP zlib publish; never path-as-content

## Local tip constructs (box)
| Lib | md5 | notes |
|-----|-----|-------|
| cg1 | 8f7ac0de8a084c4560d9a12f25c8c5b2 | Gen_EmitIdent `__doc__` -> `""` |
| cg2 | 9dc72a9214531a21ff78897cbe7b1e09 | getattr->callable; attr.add |
| cg4 | 4f94b5cae7bf4e25bc94fe2400731c31 | CallIndirect; type MapBuiltin; free-var stub 0; Ellipsis/NotImplemented |
| oop | bc8af2d04dd0bec87069179d45917732 | Exception/BaseException/object -> parent 0 |
| Extra | 65b7f1372710e5071410d83e537073c0 | Complex/Callable/Range/... |

## Climb
| Module | result |
|--------|--------|
| copy | **ok** |
| types | **ok** |
| **decimal** | **ok** (`__doc__`) |
| statistics | `match` leftover (feature) |
| contextlib | StopIteration |

## Gates (host)
curated **25/25**, matrix **84/84/84**, fizzbuzz **215153**, Hash **922**

## Probe counts
compile_ok **9**/17 (types copy heapq colorsys keyword quopri bisect abc **decimal**)
fail: statistics(match) enum/fractions/functools(SIGSEGV parse) contextlib(StopIteration)
aimacro_fail: numbers operator dataclasses

## MCP publish state
- cg2/cg4/oop/Extra zlib assembled; remote md5s MATCH local targets
- cg1 `__doc__` zlib + manifest.z.b64 pushed; awaiting assemble

## Ladder next
1. contextlib StopIteration
2. statistics match / enum parse SIGSEGV
3. numbers/operator/dataclasses aimacro_fail

Self-Hosting: not pushed.
