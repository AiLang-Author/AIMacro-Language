# AIMacro Status Scorecard

**Last updated:** 2026-09-26. Tip is `grokasaurus2` merged to `main` (codegen overnight + empty_module + exception names). Grokbot is **off** the workflow. `AIMacro/restore_staging/` is deleted.

## Gates (this box, py3.11 / 585)

| Gate | Result |
|------|--------|
| curated | **25/25** |
| original matrix | **62/62/62** |
| lib transpile | **566/585** (in-scope **392/395**) |
| compile probe (26 stdlib modules) | **21/26** (was 0/26) |
| Hash | **922** |
| fizzbuzz ELF | **215161** (was 211054; runtime grew with Extra/codegen) |

In-scope transpile fails (3): `code.py`, `multiprocessing/forkserver.py`, `xmlrpc/client.py`.

Compile probe leftovers: `posixpath` SIGSEGV, `tokenize` transpile, `traceback` `expr`, `hashlib` `translate` (method), `socket` `AddressFamily`.

## Notes

- Empty `__init__.py` emit `pass` via `py2aim`.
- Exception type idents (`AttributeError`, `BaseException`, …) and `AF_INET` emit as ints.
- `AIMacro.Translate` stub in Extra (2-arg). hashlib still emits an unbound `translate` in some paths.
