# AIMacro overnight compile — STATUS (2026-09-25)

## Tip constructs
| Construct | notes |
|-----------|-------|
| unary_plus / matmul | numbers + operator ok |
| fstring_nested_quotes | Lex_ReadFString + Parse_ExprFromSource; }} only at depth 0 |
| match/case (+ guards) | py2aim desugars to if/elif (None / Type(x) / capture / `_` / `if` guard) |

## Probe
aimacro_ok **17**/17 — dataclasses match/case cleared
ailang_ok **16**/17 — dataclasses leftover: tuple-unpack `(a,b)=f()` → `std_init_fields` unbound

## Gates
curated 25/25 (host) · Hash 922 · matrix pending this push

Self-Hosting: not pushed.
