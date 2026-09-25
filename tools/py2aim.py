#!/usr/bin/env python3
"""Temporary tip loader: expands tools/py2aim.py from assembled_py2aim.z.b64.

Real tip md5 fddbddcdc64e500b26dd161706f6bb57. Replace via MCP push_py2aim_FULL.json.
"""
from __future__ import annotations

import base64
import pathlib
import runpy
import sys
import zlib

_HERE = pathlib.Path(__file__).resolve()
_B64 = _HERE.parents[1] / "AIMacro" / "restore_staging" / "assembled_py2aim.z.b64"
_MARKER = "assembled_py2aim.z.b64"


def _maybe_expand() -> bool:
    if not _B64.is_file():
        return False
    text = _HERE.read_text(encoding="utf-8", errors="replace")
    if _MARKER not in text:
        return False
    data = zlib.decompress(base64.b64decode(_B64.read_text().strip()))
    if not data.startswith(b"#!/usr/bin/env python3"):
        raise SystemExit(f"bad payload in {_B64}")
    _HERE.write_bytes(data)
    return True


if _maybe_expand():
    sys.argv[0] = str(_HERE)
    raise SystemExit(runpy.run_path(str(_HERE), run_name="__main__"))

if __name__ == "__main__":
    raise SystemExit("py2aim stub: companion zb64 missing; run assemble_climb.py")
