# AIMacro overnight compile - STATUS (2026-09-25)

## Applied steering
- CONFORMANCE ONLY (no optimize/profile)
- One construct per commit
- Branch grokasaurus2 only; Self-Hosting never pushed
- MCP zlib publish; never path-as-content

## Tip construct
| Lib | md5 | notes |
|-----|-----|-------|
| cg1 | 6bd8afa6b74b191c08992a8ff3d29f26 | nest freevar locals + enclosing_params |
| cg2 | 425caad1469e15b10b6c7d77b370a921 | deferred freevars; MarkEnclosingLocal |
| cg3 | eddf62a25df175ba148ea38457b5b02f | lambda PushDeferred freevars |
| oop | 4c34ef07f0c596ffab9e2d77738803be | method params → enclosing; assign mark |
| ParserCore | fc21e1e34a11fc2d855ed41010f29c9d | **kwargs kept in params |

## Climb
| Module | result |
|--------|--------|
| contextlib | **ok** (method/outer freevars as nest locals) |
| statistics | `match` leftover (feature) |
| enum/fractions/functools | SIGSEGV parse |
| numbers/operator/dataclasses | aimacro_fail |

## Gates (host)
curated **25/25**, matrix **87/87/86** (compile_module_doc run SIGSEGV pre-existing), fizzbuzz **215150**, Hash **922**

## Probe counts
compile_ok **10**/17 (types copy heapq colorsys keyword quopri bisect abc decimal **contextlib**)
fail: statistics(match) enum/fractions/functools(SIGSEGV) numbers/operator/dataclasses

## Ladder next
1. statistics match / enum parse SIGSEGV
2. numbers/operator/dataclasses aimacro_fail

Self-Hosting: not pushed.
