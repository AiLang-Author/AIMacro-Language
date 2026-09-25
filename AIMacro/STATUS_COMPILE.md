# AIMacro overnight compile — STATUS (2026-09-25 cont.)

## Tip constructs
unary_plus/matmul · fstring_nested_quotes · match/case · tuple_unpack · from_import_as · for_target_unpack · DeprecationWarning · slice type · @global_enum · str.format · chained method return · unbound CallIndirect(0,) · str.encode · chain assign in method · **ValueError (+ ExcKind siblings)** · **property setter `_set` (weakref finalize_atexit)**

## Probe
aimacro_ok 17/17 · ailang_ok 17/17
expanded: pprint COMPILE_OK; encode cleared; ValueError COMPILE_OK; calendar COMPILE_OK; **weakref COMPILE_OK**
**widen compile 45/76 probed** (was ~33+ → **45** with tip aimacro.x)
leftovers: import-stubs; typing/ast aimacro fails; py LIVE 005-017; rt 0/34; construct; OOP micros 004-019
cleared: encode; pprint; cg2 39/39; ValueError; calendar; weakref dup finalize_atexit

## Gates
curated **25/25** · Hash **922** · matrix T/C 103/103 (run 102/103 pre-existing compile_module_doc SIGSEGV)

## Climb md5s (local tip installed)
| artifact | md5 | notes |
|----------|-----|-------|
| CodeGen1 | `e07214bfb6d7741ba4640757c4e13d5d` | ValueError — Library installed; manifest tip on origin |
| CodeGen2 | `3163d633ac310ba465c2dd05aecedd85` | Library installed; manifest tip on origin |
| CodeGen4 tip | `509f8ddb94e258f82660eed1acdef339` | micros 30/30; Library installed; manifest tip on origin |
| AIMacro.ailang | `23285a410951414b7664e857c2cba649` | local tip (origin old until rt micros) |
| CodeGenOOP atexit_set | `3acbe5b520760f9e0aeb3a8e6110c046` | local; micros 000-003+020 on origin |
| tools/py2aim.py LIVE | `fddbddcdc64e500b26dd161706f6bb57` | local; micros 000-004 on origin |

## MCP drain
cg2 39/39 · cg1_valueerror 17/17 · cg4 tip **30/30** · py LIVE 5/18 · rt 0/34 · oop atexit_set 5/21 · construct pending
QUEUE ~ py/rt/construct + oop 004-019
Never path-as-content. Self-Hosting: not pushed. No compiler edits. Conformance only.
Tip origin after status: (this commit)
