# AIMacro overnight compile - STATUS (2026-09-25)

## Applied steering
- CONFORMANCE ONLY (no optimize/profile)
- One construct per commit
- Branch grokasaurus2 only; Self-Hosting never pushed
- MCP zlib publish; never path-as-content

## Local tip constructs (box)
| Lib | md5 | notes |
|-----|-----|-------|
| cg1 | cf5a93c0d581890b6d25219de974d672 | StopIteration/StopAsync/BaseExceptionGroup/ExceptionGroup -> ExcKind |
| cg2 | 9dc72a9214531a21ff78897cbe7b1e09 | getattr->callable; attr.add |
| cg4 | 68e436f5aab5a65b86c13f73d840aef5 | MapTypeConstant StopIteration kinds |
| oop | bc8af2d04dd0bec87069179d45917732 | Exception/BaseException/object -> parent 0 |
| Extra | 65b7f1372710e5071410d83e537073c0 | Complex/Callable/Range/... |

## Climb
| Module | result |
|--------|--------|
| copy | **ok** |
| types | **ok** |
| decimal | **ok** (`__doc__`) |
| contextlib | StopIteration **fixed**; leftover `self` |
| statistics | `match` leftover (feature) |

## Gates (host)
curated **25/25**, matrix **85/85/85**, fizzbuzz **215153**, Hash **922**

## Probe counts
compile_ok **9**/17 (types copy heapq colorsys keyword quopri bisect abc decimal)
fail: statistics(match) contextlib(self) enum/fractions/functools(SIGSEGV parse)
aimacro_fail: numbers operator dataclasses

## MCP publish state
- cg1/cg2/cg4/oop/Extra zlib parts verified; stopit manifest.z.b64 pushed

## Ladder next
1. contextlib `self` (method param emit)
2. statistics match / enum parse SIGSEGV
3. numbers/operator/dataclasses aimacro_fail

Self-Hosting: not pushed.
