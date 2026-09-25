#!/usr/bin/env python3
"""Temporary tip loader: expands tools/py2aim.py from assembled_py2aim_tip.z.b64.* micros.

Real tip md5 eac63c5166ac4bbb47369bea173bd40a. Prefer tip_direct.push.json when MCP can carry full file.
"""
from __future__ import annotations

import base64
import pathlib
import runpy
import sys
import zlib

_HERE = pathlib.Path(__file__).resolve()
_STAGING = _HERE.parents[1] / "AIMacro" / "restore_staging"
_MARKER = "assembled_py2aim_tip.z.b64"


def _maybe_expand() -> bool:
    parts = sorted(_STAGING.glob("assembled_py2aim_tip.z.b64.[0-9][0-9][0-9]"))
    if not parts:
        return False
    text = _HERE.read_text(encoding="utf-8", errors="replace")
    if _MARKER not in text:
        return False
    b64 = "".join(p.read_text() for p in parts)
    data = zlib.decompress(base64.b64decode(b64))
    if not data.startswith(b"#!/usr/bin/env python3"):
        raise SystemExit(f"bad payload in tip micros under {_STAGING}")
    _HERE.write_bytes(data)
    return True


if _maybe_expand():
    sys.argv[0] = str(_HERE)
    raise SystemExit(runpy.run_path(str(_HERE), run_name="__main__"))

if __name__ == "__main__":
    raise SystemExit("py2aim stub: tip micros missing; climb assembled_py2aim_tip.z.b64.*")
