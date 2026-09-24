# AIMacro overnight compile — STATUS (2026-09-24 late)

## Applied steering
- CONFORMANCE ONLY (no optimize/profile)
- AILang expression sourced from AiLang-Author docs (PYTHON_GAP AddressOf/CallIndirect)
- One construct per commit

## Local (box) — green
| Construct | SHA | Repro | Notes |
|-----------|-----|-------|-------|
| compile_map_builtin | `5987a9b` | `AIMacro_Tests/compile_map_builtin.aim` → prints `3` | Gen_MapBuiltin map→AIMacro.Map; CallIndirect per elem |
| compile_iter_builtin | `cd6f726` | `AIMacro_Tests/compile_iter_builtin.aim` → `3` then `2` | Gen_MapBuiltin iter→AIMacro.Iter; IDENT builtins emit AddressOf(mapped) |

Gates (host): curated **25/25**, matrix **71/71/71**, fizzbuzz **211054**, Hash **922**.
Probe colorsys+keyword+quopri still **3/3**.

## Origin publish
- No git HTTPS push (no credentials). MCP `push_files` / zlib staging used for small files.
- Large Library.AIMacro.ailang / CodeGen4 (~100KB) not yet assembled on origin tip `532dcee` (staging partial/orphan parts from overnight MCP).
- **Action needed:** finish zlib assemble of HEAD libs (md5 lib=`037e45230fdc2d5e56b6899f41c46d77` cg4=`76542a39e86c581b6f19915654025c08`) OR MCP-push the two Library files when large-body path works.

## heapq ladder (local aimacro.x with Map+Iter)
1. ~~Unknown function: map~~ → fixed
2. ~~Variable not found: iter~~ → fixed  
3. **NEXT: Unknown function: next**

Self-Hosting: not pushed.
