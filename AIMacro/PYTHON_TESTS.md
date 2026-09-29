# AIMacro vs CPython tests (test262 analog)

JS has `test262` + `tools/test262_runner.py` + `JS-tests/test262_harness.ailang`.
AIMacro’s counterpart is CPython 3.11 `Lib/test` regrtest: preprocess → AOT
compile → run TestCase methods → JSON. On this box that is **568** files.
Pass is ELF exit 0 after those methods run. ran-0 is FAIL.

## Pieces

| JS (test262) | AIMacro |
|--------------|---------|
| test262 checkout | CPython stdlib (`--cpython`, default this python) |
| throw/async preprocessor | `tools/py2aim.py` (indent → `{ }`) |
| `test262_harness.x` | `./aimacro.x` + `./ailang.x` |
| `tools/test262_runner.py` | `tools/aimacro_cpython_runner.py` |

## Run the grind

`results/grind_db.json` is the living database. Passing files are dropped from
the default grind. Fix a batch of 10, then the next 10. When remaining is
empty, `--full` rechecks all 568.

```bash
python3 tools/aimacro_cpython_runner.py --only @results/batch10.txt --verbose
python3 tools/aimacro_cpython_runner.py --verbose
python3 tools/aimacro_cpython_runner.py --full \
    --output-json results/aimacro_regrtest.json \
    --output-md AIMacro/CONFORMANCE.md
```

`./AIMacro/scripts/run_conformance.sh` is the remaining grind. One `ailang.x`
at a time, `RLIMIT_AS` 4 GiB, 2 s CPU and 2 s wall per child. Longer than that
is a stall or a perf hole.

See [CONFORMANCE.md](CONFORMANCE.md).

## Wave 16

`print(sep=, end=)`, `list(range(5, 0, -1))`, `list("ab")`. Curated: `print_range_list.py`.

## Wave 15

`f(b=2, a=1)` and defaults via keywords. Curated: `kwargs_user.py`.

## Wave 14

`input()` vs CPython with a sibling `.stdin` file. Curated: `input_fn.py`.

## Wave 13

`sorted(xs, key=lambda n: 0-n)` and `reverse=True`. Curated: `sorted_key.py`.

## Wave 12

`1 if 1 else 0`, nested ternary, `lambda v: 1 if v else 0`. Curated: `ternary.py`.

## Wave 11

`f = lambda x: x+1; print(f(3))` and `(lambda a, b: a*b)(3, 4)`. No closures.
Curated: `lambda_fn.py`.

## Wave 10

`print({"z": 1, "a": 2})` is `{'z': 1, 'a': 2}`. Curated: `dict_order.py`.

## Wave 9

`0 and boom()` / `1 or boom()` / `5 < 3 < boom()` do not call `boom`.
Curated: `short_circuit.py`.

## Wave 8

`print(1 == 1)` is `True`; `1 and 2` is `2`; `in`/`is`/`not`/`isinstance`/`any`/`all`
match CPython. Curated: `compare_bool.py`.

## Wave 7

`print(True)`, `print([1, 2])`, `print({"a": 1})`, `repr(x)`, and
`json.dumps({"k": "v"})` match CPython stdout. Curated: `print_repr.py`.

Grow `tests/python/curated/` the way JS grew midgate, then slice CPython
`Lib/test/test_grammar.py`-style files — not 50k tests on day one.
