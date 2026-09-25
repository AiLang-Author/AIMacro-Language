# AIMacro overnight compile — STATUS (2026-09-25 cont.)

## Tip constructs
unary_plus/matmul · fstring_nested_quotes · match/case · tuple_unpack · from_import_as · for_target_unpack · DeprecationWarning · slice type · @global_enum · str.format · chained method return · unbound CallIndirect(0,) · str.encode · chain assign in method · ValueError (+ ExcKind siblings) · property setter `_set` (weakref finalize_atexit) · **Warning ExcKind siblings (ImportWarning/EncodingWarning/…)** · **str.encode MapMethod → AIMacro.Encode (calendar)**

## Probe
aimacro_ok 17/17 · ailang_ok 17/17
expanded: pprint COMPILE_OK (prior); encode cleared; ValueError COMPILE_OK; calendar COMPILE_OK; weakref COMPILE_OK; **warnings COMPILE_OK**
**widen compile 47/76 probed** (was 45 → **47** with Warning ExcKind + Encode MapMethod)
leftovers: import-stubs; typing/ast/turtle/configparser aimacro fails; pprint max_width; gettext reverse; Expected ')' chain; module-level consts
cleared this stretch: py LIVE 18/18; rt 34/34; oop atexit_set micros verified; warnings; calendar encode

## Gates
curated **25/25** (pending re-gate this tip) · Hash **922** · matrix T/C prior 103/103

## Climb md5s (local tip installed)
| artifact | md5 | notes |
|----------|-----|-------|
| CodeGen1 | `37d1791141b42600d87525d8e8b97560` | Warning ExcKind siblings |
| CodeGen2 | `773eec2c8e04b52d20bca5e1202ee3d4` | encode/decode is_builtin |
| CodeGen4 tip | `d440089ab74609d75741c2e3a0ead172` | MapMethod Encode/Decode |
| AIMacroExtra | `e65c424621b959db2288b26074d67eb9` | Encode/Decode stubs |
| AIMacro.ailang | `23285a410951414b7664e857c2cba649` | rt tip installed |
| CodeGenOOP atexit_set | `3acbe5b520760f9e0aeb3a8e6110c046` | local tip; micros 000-020 on origin |
| tools/py2aim.py LIVE | `fddbddcdc64e500b26dd161706f6bb57` | LIVE micros 000-017 on origin |

## MCP drain
cg2 39/39 · cg1 VE prior · cg4 tip 30/30 · **py LIVE 18/18** · **rt 34/34** · oop atexit_set 21/21 · Extra encode micros on origin
QUEUE ~ Library tip install (assemble) + cg1/cg2/cg4 Warning+Encode patches + construct leftovers
Never path-as-content. Self-Hosting: not pushed. No compiler edits. Conformance only.
Tip origin after status: (this commit)
