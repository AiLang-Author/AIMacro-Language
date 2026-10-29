# AIMacro CPython conformance scorecard

Generated **2026-10-29**. Python 3.11.6. Stdlib `/home/bob/tools/oss-cad-suite/lib/python3.11`.

The grind is CPython 3.11 `Lib/test` regrtest (568 files on this box). Pass is ELF exit 0 after TestCase.test* methods run. ran-0 is FAIL.

## Suite

| Suite | Stage | Total | Pass | Fail | Skip | Seconds |
|-------|-------|------:|-----:|-----:|-----:|--------:|
| `test` | run | 568 | 310 | 258 | 0 | 2140.083 |

## Fail stages

- **test:** run=242, compile=8, transpile=8

`test_unary.py` was rechecked after the integer-minus-float fix and now passes. `test_time.py` was rechecked after the class-body order fix and now passes. The living database is 312 pass and 256 fail. Those rechecks are not a new full-suite timing.

## Compared with 2026-10-12

The October 12 database was 318 pass and 250 fail (run 167, compile 80, transpile 3). This run gained 22 passes and lost 30. Compile failures fell from 80 to 8. Net pass is down 8 because files that used to die in the compiler now run and still fail, and 30 former passes broke. The queue is [BACKLOG.md](BACKLOG.md). Speed is parked.

## How to re-run

```bash
python3 tools/aimacro_cpython_runner.py --verbose
python3 tools/aimacro_cpython_runner.py --full \
    --output-json results/aimacro_regrtest.json \
    --output-md AIMacro/CONFORMANCE.md
```

`--full` rewrites `results/grind_db.json` and `results/pass.txt`. The runner's `--output-md` replaces this file with the table only. Put the comparison back from [BACKLOG.md](BACKLOG.md) after a regenerate.
