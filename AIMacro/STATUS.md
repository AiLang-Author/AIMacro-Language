# AIMacro Status Scorecard

**Last updated:** 2026-09-26. Tip is `grokasaurus2` merged to `main` (codegen overnight + empty_module + exception names). Grokbot is **off** the workflow. `AIMacro/restore_staging/` is deleted.

## Grind (this box, py3.11 / 568 Lib/test)

| Gate | Result |
|------|--------|
| CPython `Lib/test` regrtest | **19/568** (16 from full run + 3 from batch 10) |
| Hash | **922** |

Pass is TestCase methods actually run. ran-0 is FAIL. Passing files are
removed from the grind (`results/pass.txt`). Current batch is
`results/batch10.txt`. `--full` when remaining is empty.

## Notes

- Empty `__init__.py` emit `pass` via `py2aim`.
- Exception type idents (`AttributeError`, `BaseException`, …) and `AF_INET` emit as ints.
- `AIMacro.Translate` stub in Extra (2-arg). hashlib still emits an unbound `translate` in some paths.
