# AIMacro overnight compile — STATUS (2026-09-25)

## Tip constructs
| Construct | notes |
|-----------|-------|
| unary_plus / matmul | numbers + operator ok |
| fstring_nested_quotes | Lex_ReadFString + Parse_ExprFromSource; }} only at depth 0 |
| match/case (+ guards) | py2aim desugars to if/elif (None / Type(x) / capture / `_` / `if` guard) |
| tuple_unpack assign | py2aim AST desugar `(a,b)=f()` → `_aim_unpack_N` + index binds |

## Probe
aimacro_ok **17**/17 · ailang_ok **17**/17 — dataclasses cleared (match/case + tuple unpack)
expanded aimacro **22**/23 (html package on 3.13); ailang 17/23 (import deps)

## Gates
curated 25/25 · Hash 922 · matrix transpile/compile expected green

## Tip17 MCP
micros in `/workspace/mcp_mega_need/` (25 packs). Verify via **commit-SHA** raw URL (branch raw CDN stale).
Manifest LAST after all micros MATCH. assemble joins name.000+ and restores tools/py2aim.py.
Core added to manifest md5=bad17cc74bd271875fe2db5a833f8f2b.

Self-Hosting: not pushed.
