#!/usr/bin/env python3
"""
aimacro_cpython_runner.py — CPython 3.11 Lib/test conformance grind.

The score is CPython Lib/test (regrtest shape, 568 files on 3.11): transpile,
compile, run TestCase.test* methods. ran-0 is FAIL. Skip tags are not a pass.

Pipeline per file (one ailang.x at a time, RLIMIT_AS 4GiB, RLIMIT_CPU 60s):
  1. py2aim.py     indent Python → AIMacro `{ }`
  2. ./aimacro.x   .aim → .ailang
  3. ./ailang.x    compile
  4. run the ELF; UnittestDone ProcessExit(1) if scheduled tests did not run

Usage:
    python3 tools/aimacro_cpython_runner.py --verbose
    python3 tools/aimacro_cpython_runner.py --output-json results/aimacro_regrtest.json

Copyright (c) 2026 Sean Collins, 2 Paws Machine and Engineering. SCSL.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import resource
import signal
import subprocess
import sys
import sysconfig
import tempfile
import time
from collections import Counter
from datetime import date
from pathlib import Path

# One ailang.x at a time. 4 GiB AS / 60s CPU per child so a compile cannot
# swap-thrash the box (previous 568-file run hard-locked at swap_reclaim).
RSS_AS_BYTES = 4 * 1024 * 1024 * 1024
CPU_SEC = 60
LOCK_PATH = Path("/tmp/aimacro-runner.lock")

ROOT = Path(__file__).resolve().parents[1]
AIMACRO = ROOT / "aimacro.x"
AILANG = ROOT / "ailang.x"
PY2AIM = ROOT / "tools" / "py2aim.py"
PYTHON = sys.executable


def _limit_child() -> None:
    # start_new_session already setsid(); a second setsid() raises and aborts spawn.
    resource.setrlimit(resource.RLIMIT_AS, (RSS_AS_BYTES, RSS_AS_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_SEC, CPU_SEC + 5))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run_cmd(
    cmd: list[str],
    timeout: float,
    cwd: Path | None = None,
    stdin_text: str | None = None,
) -> tuple[int, str, str]:
    try:
        p = subprocess.Popen(
            cmd,
            cwd=cwd or ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            preexec_fn=_limit_child,
        )
    except OSError as e:
        return 127, "", str(e)
    try:
        out, err = p.communicate(stdin_text, timeout=timeout)
        return p.returncode if p.returncode is not None else 137, out, err
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            p.kill()
        try:
            out, err = p.communicate(timeout=2)
        except Exception:
            out, err = "", "timeout"
        return 124, out or "", (err or "") + "timeout"


def stdin_for(src: Path) -> str | None:
    p = src.with_suffix(".stdin")
    if p.is_file():
        return p.read_text(encoding="utf-8")
    return None


def read_source(src: Path) -> tuple[str | None, str | None]:
    raw = src.read_bytes()
    if b"\0" in raw[:4096]:
        return None, "binary"
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc), None
        except UnicodeDecodeError:
            continue
    return None, "encoding"


def feature_tags(src_text: str) -> list[str]:
    return []


def py2aim_text(src_text: str, dest: Path) -> tuple[int, str]:
    rc, out, err = run_cmd(
        [PYTHON, str(PY2AIM), "--stdin"],
        15,
        stdin_text=src_text,
    )
    if rc != 0:
        return rc, err or out
    dest.write_text(out, encoding="utf-8")
    return 0, ""


def py2aim(src: Path, dest: Path) -> tuple[int, str]:
    rc, out, err = run_cmd([PYTHON, str(PY2AIM), str(src), str(dest)], 10)
    return rc, err or out


def run_cpython(src: Path, timeout: float) -> tuple[int, str]:
    rc, out, err = run_cmd([PYTHON, str(src)], timeout, stdin_text=stdin_for(src))
    return rc, out


def unique_stem(src: Path, root: Path) -> str:
    try:
        rel = src.relative_to(root)
    except ValueError:
        rel = Path(src.name)
    return "__".join(rel.with_suffix("").parts)


def run_aimacro_stage(
    aim: Path,
    timeout: float,
    work: Path,
    stage: str,
    src: Path | None = None,
    stem: str | None = None,
) -> tuple[int, str, str, str]:
    """Returns (rc, stdout, err, fail_stage). fail_stage is transpile|compile|run|''."""
    name = stem or aim.stem
    ailang_out = work / (name + ".ailang")
    bin_out = work / name
    rc, out, err = run_cmd(
        [str(AIMACRO), str(aim), str(ailang_out)], timeout, cwd=ROOT
    )
    if rc != 0:
        return rc, "", f"transpile: {(out or '')[-300:]}\n{(err or '')}".strip(), "transpile"
    if stage == "transpile":
        return 0, "", "", ""
    rc, out, err = run_cmd(
        [str(AILANG), str(ailang_out), str(bin_out)], timeout, cwd=ROOT
    )
    if rc != 0:
        # ailang.x prints parse/codegen errors on stdout; SIGSEGV is rc < 0.
        blob = ((out or "") + "\n" + (err or "")).strip()
        return rc, "", f"compile: {blob[-800:]}", "compile"
    if stage == "compile":
        return 0, "", "", ""
    os.chmod(bin_out, 0o755)
    feed = stdin_for(src) if src is not None else stdin_for(aim)
    rc, out, err = run_cmd([str(bin_out)], timeout, cwd=ROOT, stdin_text=feed)
    if rc != 0:
        return rc, out, err, "run"
    return rc, out, err, ""


def run_aimacro(aim: Path, timeout: float, work: Path, src: Path | None = None) -> tuple[int, str, str]:
    rc, out, err, _ = run_aimacro_stage(aim, timeout, work, "run", src)
    return rc, out, err


def default_stdlib() -> Path:
    p = Path(sysconfig.get_path("stdlib"))
    return p


TEST_EXCLUDE_DIRS = {
    "crashers",
    "leakers",
    "dtracedata",
    "encoded_modules",
    "tokenizedata",
    "typinganndata",
    "ziptestdata",
    "libregrtest",
    "support",
    "data",
    "audiodata",
    "imghdrdata",
    "sndhdrdata",
    "xmltestdata",
    "tracedmodules",
}


def discover_test(stdlib: Path) -> list[Path]:
    test_dir = stdlib / "test"
    if not test_dir.is_dir():
        return []
    files: list[Path] = []
    for p in test_dir.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(test_dir)
        if any(part in TEST_EXCLUDE_DIRS for part in rel.parts[:-1]):
            continue
        if p.name.startswith("test_"):
            files.append(p)
        elif (
            p.name == "__init__.py"
            and p.parent != test_dir
            and p.parent.name.startswith("test_")
        ):
            files.append(p)
    return sorted(files)


def summarize(results: list[dict], seconds: float) -> dict:
    ok = sum(1 for r in results if r["status"] == "pass")
    fail = sum(1 for r in results if r["status"] == "fail")
    skip = sum(1 for r in results if r["status"] == "skip")
    by_stage: Counter[str] = Counter()
    skip_reasons: Counter[str] = Counter()
    for r in results:
        if r["status"] == "fail":
            by_stage[r.get("stage") or "unknown"] += 1
        if r["status"] == "skip":
            skip_reasons[r.get("reason") or "unknown"] += 1
    return {
        "ok": ok,
        "fail": fail,
        "skip": skip,
        "total": len(results),
        "seconds": round(seconds, 3),
        "fail_stages": dict(by_stage),
        "skip_reasons": dict(skip_reasons),
        "results": results,
    }


def run_suite(
    files: list[Path],
    stage: str,
    timeout: float,
    work: Path,
    verbose: bool,
    name_root: Path,
    limit: int | None,
) -> dict:
    if limit is not None:
        files = files[: max(0, limit)]
    results: list[dict] = []
    t0 = time.time()
    n = len(files)
    for i, src in enumerate(files, 1):
        try:
            rel = str(src.relative_to(ROOT) if src.is_relative_to(ROOT) else src)
        except AttributeError:
            rel = str(src)
        text, why = read_source(src)
        if text is None:
            rec = {"file": rel, "status": "skip", "reason": why, "tags": []}
            results.append(rec)
            if verbose:
                print(f"SKIP {rel} ({why})")
            continue
        tags = feature_tags(text)
        stem = unique_stem(src, name_root)
        aim = work / (stem + ".aim")
        rc, err = py2aim_text(text, aim)
        if rc != 0:
            rec = {
                "file": rel,
                "status": "fail",
                "stage": "py2aim",
                "err": (err or "")[-500:],
                "tags": tags,
            }
            results.append(rec)
            print(f"FAIL {rel} py2aim")
            continue
        rc, am_out, am_err, fail_stage = run_aimacro_stage(
            aim, timeout, work, stage, src, stem=stem
        )
        # drop artifacts so /tmp does not fill
        for leftover in (aim, work / (stem + ".ailang"), work / stem):
            try:
                leftover.unlink()
            except FileNotFoundError:
                pass
        if rc != 0:
            rec = {
                "file": rel,
                "status": "fail",
                "stage": fail_stage or "aimacro",
                "rc": rc,
                "err": (am_err or "")[-500:],
                "out": (am_out or "")[-300:],
                "tags": tags,
            }
            results.append(rec)
            print(f"FAIL {rel} {rec['stage']} rc={rc}", flush=True)
            continue
        ran_m = re.search(r"unittest: ran (\d+) tests", am_out or "")
        ran_n = int(ran_m.group(1)) if ran_m else 0
        if stage == "run" and ran_n == 0:
            rec = {
                "file": rel,
                "status": "fail",
                "stage": "run",
                "rc": 0,
                "err": "no tests ran",
                "out": (am_out or "")[-300:],
                "tags": tags,
            }
            results.append(rec)
            print(f"FAIL {rel} run no tests", flush=True)
            continue
        rec = {"file": rel, "status": "pass", "tags": tags, "stage_ok": stage}
        results.append(rec)
        if verbose:
            print(f"OK   {rel}")
        if not verbose and (i % 25 == 0 or i == n):
            print(f"  [{i}/{n}] {rel}", flush=True)
    return summarize(results, time.time() - t0)


def format_suite_line(name: str, s: dict) -> str:
    return (
        f"{name:<10} total={s['total']:<5} ok={s['ok']:<5} fail={s['fail']:<5} "
        f"skip={s['skip']:<5} {s['seconds']:.1f}s"
    )


def format_scorecard(payload: dict) -> str:
    lines = [
        "# AIMacro CPython conformance scorecard",
        "",
        f"Generated **{payload.get('generated')}**. "
        f"Python {payload.get('python')}. "
        f"Stdlib `{payload.get('cpython_lib')}`.",
        "",
        "The grind is CPython 3.11 `Lib/test` regrtest (568 files on this box). "
        "Pass is ELF exit 0 after TestCase.test* methods run. ran-0 is FAIL.",
        "",
        "## Suite",
        "",
        "| Suite | Stage | Total | Pass | Fail | Skip | Seconds |",
        "|-------|-------|------:|-----:|-----:|-----:|--------:|",
    ]
    for name, s in (payload.get("suites") or {}).items():
        lines.append(
            f"| `{name}` | {s.get('stage', '')} | {s['total']} | {s['ok']} | "
            f"{s['fail']} | {s['skip']} | {s['seconds']} |"
        )
    lines.extend(["", "## Fail stages", ""])
    for name, s in (payload.get("suites") or {}).items():
        fs = s.get("fail_stages") or {}
        if not fs:
            continue
        bits = ", ".join(f"{k}={v}" for k, v in fs.items())
        lines.append(f"- **{name}:** {bits}")
    lines.extend(
        [
            "",
            "## How to re-run",
            "",
            "```bash",
            "python3 tools/aimacro_cpython_runner.py --verbose",
            "python3 tools/aimacro_cpython_runner.py \\",
            "    --output-json results/aimacro_regrtest.json \\",
            "    --output-md AIMacro/CONFORMANCE.md",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--output-json", type=Path)
    ap.add_argument("--output-md", type=Path)
    ap.add_argument(
        "--cpython",
        type=Path,
        help="CPython stdlib root (Lib/). Default: this python's stdlib.",
    )
    ap.add_argument(
        "--stage",
        choices=["run", "compile", "transpile"],
        default="run",
        help="Pipeline stop. Default run: transpile, compile, execute TestCase methods.",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap files. Omit for all. 0 means zero files.",
    )
    args = ap.parse_args()

    lock_f = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("error: another aimacro runner holds /tmp/aimacro-runner.lock", file=sys.stderr)
        return 3

    if not AIMACRO.is_file() or not AILANG.is_file():
        print("error: need ./aimacro.x and ./ailang.x", file=sys.stderr)
        return 2

    stdlib = args.cpython if args.cpython else default_stdlib()
    files = discover_test(stdlib)
    if not files:
        print(f"error: no Lib/test files under {stdlib}", file=sys.stderr)
        return 2

    payload = {
        "generated": date.today().isoformat(),
        "python": sys.version.split()[0],
        "cpython_lib": str(stdlib),
        "suites": {},
    }
    with tempfile.TemporaryDirectory(prefix="aimacro_regrtest_") as td:
        work = Path(td)
        stage = args.stage
        print(f"=== test stage={stage} files={len(files)} ===", flush=True)
        summary = run_suite(
            files,
            stage,
            args.timeout,
            work,
            args.verbose,
            stdlib,
            args.limit,
        )
        summary["stage"] = stage
        slim = dict(summary)
        slim["results"] = [
            {k: v for k, v in r.items() if k not in ("python", "aimacro")}
            for r in summary["results"]
        ]
        payload["suites"]["test"] = slim
        print("---")
        print(format_suite_line("test", summary), flush=True)

    print("=== scorecard ===")
    for name, s in payload["suites"].items():
        print(format_suite_line(name, s))

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"wrote {args.output_json}")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(format_scorecard(payload))
        print(f"wrote {args.output_md}")
    return 0 if payload["suites"]["test"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
