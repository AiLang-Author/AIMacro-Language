# AIMacro overnight compile — STATUS (2026-09-25)

## Applied steering
- CONFORMANCE ONLY (no optimize/profile)
- One construct per commit
- Branch grokasaurus2 only; Self-Hosting never pushed
- MCP zlib publish; never path-as-content

## Local tip constructs (box)
| Lib | md5 | notes |
|-----|-----|-------|
| cg2 | 9dc72a9214531a21ff78897cbe7b1e09 | getattr→callable; attr.add |
| cg4 | 4f94b5cae7bf4e25bc94fe2400731c31 | CallIndirect; type MapBuiltin; free-var stub 0; Ellipsis/NotImplemented |
| oop | bc8af2d04dd0bec87069179d45917732 | Exception/BaseException/object → parent 0 |
| Extra | 65b7f1372710e5071410d83e537073c0 | Complex/Callable/Range/… |

## Climb
| Module | result |
|--------|--------|
| copy | **ok** |
| **types** | **ok** |
| statistics | `match` leftover (feature) |

## Gates (host)
curated **25/25**, matrix **85/85/85**, fizzbuzz **215153**, Hash **922**

## Probe counts
compile_ok **8**/17 (types copy heapq colorsys keyword quopri bisect abc)
fail: statistics(match) enum/fractions/functools(SIGSEGV parse) decimal(__doc__) contextlib(StopIteration)
aimacro_fail: numbers operator dataclasses

## MCP publish state
- Extra zlib parts published; Library.AIMacroExtra on remote still placeholder until assemble/restore
- cg2 zlib 00-02 + 06.9-07.3 published; ~131 parts remain
- cg4/oop zlib need republish after func/Ellipsis climb
- manifest not yet pushed

## Ladder next
1. Finish remaining zlib parts + manifest → assemble
2. MCP restore Extra.ailang over placeholder
3. statistics match / enum parse / decimal __doc__

Self-Hosting: not pushed.
