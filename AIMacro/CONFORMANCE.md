# AIMacro CPython conformance scorecard

Generated **2026-09-29**. Python 3.11.6. Stdlib `/home/bob/tools/oss-cad-suite/lib/python3.11`.

The grind is CPython 3.11 `Lib/test` regrtest (568 files on this box). Pass is ELF exit 0 after TestCase.test* methods run. ran-0 is FAIL.

## Suite

| Suite | Stage | Total | Pass | Fail | Skip | Seconds |
|-------|-------|------:|-----:|-----:|-----:|--------:|
| `test` | run | 568 | 16 | 552 | 0 | 707.235 |

After that run, passing files are dropped from the grind. Batch 10
(`results/batch10.txt`) added `test_errno`, `test_longexp`, and
`test_future_stmt/test_future_multiple_imports` — **19** in `results/pass.txt`.
`--full` is the next whole-suite recheck.

## Fail stages

- **test:** compile=257, run=243, py2aim=25, transpile=27

## How to re-run

```bash
python3 tools/aimacro_cpython_runner.py --verbose
python3 tools/aimacro_cpython_runner.py \
    --output-json results/aimacro_regrtest.json \
    --output-md AIMacro/CONFORMANCE.md
```
