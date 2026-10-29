# AIMacro Status Scorecard

**Last updated:** 2026-10-29. Tip is `main`. The full CPython regrtest was re-run with `--full`.

## Grind (this box, py3.11 / 568 Lib/test)

| Gate | Result |
|------|--------|
| CPython `Lib/test` regrtest | **310/568** pass, 258 fail, 0 skip, 2140 s |
| Fail stages | run 242, compile 8, transpile 8 |
| October 12 | 318 pass / 250 fail (compile was 80) |

Pass is TestCase methods actually run. ran-0 is FAIL. Passing files are listed in `results/pass.txt` (310 lines). The living database is `results/grind_db.json`. The knock-off queue is [BACKLOG.md](BACKLOG.md). The table is [CONFORMANCE.md](CONFORMANCE.md).

Speed is parked. Compiler optimization and later code optimization own that.

## Notes

- Empty `__init__.py` emit `pass` via `py2aim`.
- Exception type idents (`AttributeError`, `BaseException`, …) and `AF_INET` emit as ints.
- `AIMacro.Translate` stub in Extra (2-arg). hashlib still emits an unbound `translate` in some paths.
