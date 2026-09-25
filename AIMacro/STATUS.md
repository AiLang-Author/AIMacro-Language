# AIMacro overnight compile - STATUS (2026-09-25)

## Tip constructs
| Construct | notes |
|-----------|-------|
| unary_plus / matmul | numbers + operator ok |
| fstring_nested_quotes | Lex_ReadFString + Parse_ExprFromSource; }} only at depth 0 |
| dataclasses | nested f-string ok; now fails match/case guard `case x if ...:` (py2aim left Python colons) |

## Probe
compile_ok **16**/17 — fail: dataclasses (match/case)

## Gates
recheck on host

Self-Hosting: not pushed.
