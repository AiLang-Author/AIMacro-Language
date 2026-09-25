# AIMacro overnight compile — STATUS (2026-09-25 cont.)

## Tip constructs
unary_plus/matmul · fstring_nested_quotes · match/case · tuple_unpack · from_import_as · for_target_unpack · DeprecationWarning · slice type · @global_enum · str.format · chained method return · unbound CallIndirect(0,) · str.encode · chain assign in method · **ValueError (+ ExcKind siblings)** Gen_EmitIdent ints like StopIteration

## Probe
aimacro_ok 17/17 · ailang_ok 17/17 (pre-ValueError tip)
expanded: pprint COMPILE_OK; encode cleared; ValueError COMPILE_OK; **calendar COMPILE_OK**
leftovers: widen probe (datetime/fractions/…); install CodeGen1 ValueError tip on origin
cleared: encode; pprint max_width; **cg2 climb 39/39** md5 `3163d633`; ValueError EmitIdent; calendar

## Gates
curated 25/25 · Hash 922 · matrix T/C 103/103 (run 102/103 pre-existing compile_module_doc SIGSEGV)
fizzbuzz ELF 215166

## Climb md5s (local)
| artifact | md5 |
|----------|-----|
| CodeGen1 | `e07214bfb6d7741ba4640757c4e13d5d` (ValueError) — origin Library older; micros assembled_cg1_valueerror.z.b64.000+ |
| CodeGen2 | `3163d633ac310ba465c2dd05aecedd85` assembled_cg2.z.b64 **39/39 on origin** |

## MCP drain
cg2 micro batches 02–09 drained + verified commit-SHA raw (39/39). cg1 ValueError micros + cg4/rt/py leftovers remain.
Probes deleted: _trunc_500 _trunc_2000 _size_probe_4801.
Never path-as-content. Self-Hosting: not pushed. No compiler edits. Conformance only.
