#!/usr/bin/env python3
"""py2aim.py — climb tip; materializing from assembled_py2aim.z.b64"""
import base64, pathlib, sys, zlib

def _materialize() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    b64 = (root / "AIMacro/restore_staging/assembled_py2aim.z.b64").read_text().strip()
    data = zlib.decompress(base64.b64decode(b64))
    pathlib.Path(__file__).write_bytes(data)

if __name__ == "__main__":
    # If we are still the stub, expand then re-exec.
    text = pathlib.Path(__file__).read_text(encoding="utf-8")
    if "assembled_py2aim.z.b64" in text and "desugar_match" not in text:
        _materialize()
        raise SystemExit(__import__("runpy").run_path(str(pathlib.Path(__file__).resolve()), run_name="__main__"))
    # After materialize, real main is in the expanded file; this branch is unreachable
    # on a fresh expand because re-exec replaces us. Keep a tiny CLI for safety:
    from pathlib import Path as _P
    raise SystemExit("py2aim stub: run again after materialize")
