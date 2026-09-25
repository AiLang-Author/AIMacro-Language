# AIMacro overnight compile — STATUS (2026-09-25)

## Tip constructs
| Construct | notes |
|-----------|-------|
| unary_plus / matmul | numbers + operator ok |
| fstring_nested_quotes | Lex_ReadFString + Parse_ExprFromSource; } only at depth 0 |
| match/case (+ guards) | py2aim desugars to if/elif |
| tuple_unpack assign | py2aim AST desugar |
| from_import_as | py2aim: `from M import X as Y` → bind Y (html `_html5`) |
| for_target_unpack | py2aim: `for a,b` / `for i,(x,y)` → `_aim_funpack_N` + index binds |
| DeprecationWarning | Gen_EmitIdent ExcKind stub (FutureWarning family) |
| slice type | Gen_MapTypeConstant → TypeID.UNKNOWN; Gen_EmitIdent → AddressOf(AIMacro.Slice) |

## Probe
aimacro_ok **17**/17 · ailang_ok **17**/17
expanded aimacro **23**/23 · ailang **20**/23 (slice mapped; calendar still fails)
cleared: html, string, textwrap (+ DeprecationWarning on calendar path)
leftovers: calendar `Variable not found: FEBRUARY`; base64/pprint SIGSEGV `Expected ')' after arguments`

## Gates
curated **25**/25 · Hash **922** · matrix transpile/compile **99**/99 (run 98/99 pre-existing `compile_module_doc` SIGSEGV)
Fizzbuzz size not gated this shift.

## Tip17
Library md5s MATCH origin assemble. py2aim on tip17 assemble was stale (missing match/tuple); this push restores tip desugars + new ones.

Self-Hosting: not pushed. No compiler edits. Conformance only.
