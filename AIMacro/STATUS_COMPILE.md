# STATUS_COMPILE (grokasaurus2)

## Widen probe
**56/76** (was 52; prior stretch 54 with enum lost; now +enum +locale, no losses vs 54)

Gained this stretch vs 52: gettext, gzip, mimetypes, enum, locale (+maybe others already in 54).

## Constructs
- CodeGen2 `Gen_MarkBodyAssignVars` recurse IF/WHILE/FOR (gettext `op`)
- CodeGen2 MethodCall flatten `Node.SLICE_ACCESS` (gzip `do.unused_data[8:].lstrip`)
- py2aim multiline `yield`/`yield from` stub (enum Flag; bare yield MINUS_ASSIGN)
- py2aim `desugar_nameerror_probe` (`try: CODESET` / locale)
- py2aim PEP695 / `**kwargs` ann / yield (typing+ast aimacro parse; ailang leftovers)

## Origin Libraries (target tip md5s)
| Lib | tip md5 | origin |
|-----|---------|--------|
| cg1 | 37d17911… | OK |
| OOP | 7646560a… | OK |
| Extra | e65c4246… | OK |
| cg3 | 9672189e… | assembling |
| cg2 | 5c3da1fb… (markslice) | climbing |
| cg4 | 91254a26… | climbing |
| rt | c1532629… | climbing |

## Hash
922 (host)

## Self-Hosting
not pushed

## Next
Finish climb cg2_markslice / cg4_reverse / rt_listreverse; tip-manifest; verify origin md5s; typing/ast ailang leftovers.
