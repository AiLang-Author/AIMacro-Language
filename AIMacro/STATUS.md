# AIMacro overnight compile — STATUS (2026-09-25)

## Tip constructs
| Construct | notes |
|-----------|-------|
| unary_plus / matmul | numbers + operator ok |
| fstring_nested_quotes | Lex_ReadFString + Parse_ExprFromSource; }} only at depth 0 |
| match/case (+ guards) | py2aim desugars to if/elif (None / Type(x) / capture / `_` / `if` guard) |

## Probe
aimacro_ok **17**/17 — dataclasses match/case cleared
ailang_ok **16**/17 — leftover: tuple-unpack `(a,b)=f()` → `std_init_fields` unbound
expanded aimacro **23**/23 ( +textwrap,string,pprint,calendar,html,base64 ); ailang 16/23

## Gates
curated 25/25 · Hash 922 · matrix transpile/compile 92/92 (run: compile_module_doc.aim host segfault — pre-existing, not py2aim)

## Tip17 MCP
zlib micros + Core + py2aim staging queued under /workspace/mcp_mega/; assemble joins name.000+ and restores tools/py2aim.py. Manifest LAST.
Remote: STATUS+test pushed; libs still stale until megas+manifest land.

Self-Hosting: not pushed.
