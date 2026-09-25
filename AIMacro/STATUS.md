# AIMacro overnight compile — STATUS (2026-09-25)

## Tip constructs
| Construct | notes |
|-----------|-------|
| unary_plus / matmul | numbers + operator ok |
| fstring_nested_quotes | Lex_ReadFString + Parse_ExprFromSource; } only at depth 0 |
| match/case (+ guards) | py2aim desugars to if/elif |
| tuple_unpack assign | py2aim AST desugar |
| from_import_as | py2aim: `from M import X as Y` → bind Y |
| for_target_unpack | py2aim: `for a,b` / nested → `_aim_funpack_N` |
| DeprecationWarning | Gen_EmitIdent ExcKind stub |
| slice type | TypeID.UNKNOWN / AddressOf(AIMacro.Slice) |
| @global_enum | CodeGen2 → FixedPool.PyMod exports (calendar FEBRUARY) |
| str.format | CodeGen4 StringFormat0..4 (was NumMod illegal arity) |
| chained method return | CodeGen2 Gen_Return flatten receiver |
| unbound CallIndirect(0,) | CodeGen4 → Types.GetNone() |

## Probe
aimacro_ok **17**/17 · ailang_ok **17**/17
expanded aimacro **23**/23 · ailang ~**21**/23 (base64 compile cleared this stretch)
leftovers: calendar `Unknown function: encode`; pprint `Variable not found: max_width`
cleared: FEBRUARY; base64/pprint SIGSEGV `Expected ')' after arguments`

## Gates
curated **25**/25 · Hash **922** · matrix transpile/compile **100**/100 (run 99/100 pre-existing `compile_module_doc` SIGSEGV)

## Climb / tip md5s (local)
| artifact | md5 |
|----------|-----|
| CodeGen1 | `b65521dbdf5989419ee8346b920cf3a6` |
| CodeGen2 | `3163d633ac310ba465c2dd05aecedd85` |
| CodeGen4 | `509f8ddb94e258f82660eed1acdef339` (diverged from climb tip 6b985870… by format/CallIndirect) |
| AIMacro.ailang | `23285a410951414b7664e857c2cba649` |
| tools/py2aim.py | `fddbddcdc64e500b26dd161706f6bb57` |

Companions: `AIMacro/restore_staging/assembled_{cg2,cg4_tip,aimacro_rt}.z.b64`. Origin py2aim may still be expand-stub; verify via commit-SHA raw. Full tip: `/workspace/mcp_climb/push_py2aim_LIVE.json`.

Self-Hosting: not pushed. No compiler edits. Conformance only.
