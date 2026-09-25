#!/usr/bin/env python3
import base64, zlib, pathlib, json, hashlib, sys
root = pathlib.Path(__file__).resolve().parents[2]
st = root / "AIMacro" / "restore_staging"
mz = st / "manifest.z.b64"
if mz.exists():
    data = zlib.decompress(base64.b64decode(mz.read_text().strip()))
    (st / "manifest.json").write_bytes(data)
    print(f"restored manifest.json {len(data)} bytes from manifest.z.b64")
manifest = json.loads((st / "manifest.json").read_text())

def read_part(name: str) -> str:
    """Read staging part; if name.000+ microchunks exist, join them (exact MCP-safe path)."""
    micros = sorted(st.glob(name + ".[0-9][0-9][0-9]"))
    if micros:
        text = "".join(p.read_text() for p in micros)
        print(f"  joined {len(micros)} microchunks for {name} -> {len(text)} chars")
        return text
    path = st / name
    if not path.exists():
        raise FileNotFoundError(name)
    return path.read_text()

ok = True
for m in manifest:
    b64 = "".join(read_part(p) for p in m["parts"])
    data = zlib.decompress(base64.b64decode(b64))
    got = hashlib.md5(data).hexdigest()
    out = root / "Librarys" / "AIMacro" / m["name"]
    out.write_bytes(data)
    status = "OK" if got == m["md5"] else "MD5_MISMATCH"
    if got != m["md5"]:
        ok = False
    print(f"wrote {out} {len(data)} bytes md5={got} expect={m['md5']} {status}")

# Also restore tools/py2aim.py from py2aim.z.b64.NNN micros (tip17+)
py_micros = sorted(st.glob("py2aim.z.b64.[0-9][0-9][0-9]"))
if py_micros:
    b64 = "".join(p.read_text() for p in py_micros)
    data = zlib.decompress(base64.b64decode(b64))
    outp = root / "tools" / "py2aim.py"
    outp.write_bytes(data)
    print(f"wrote {outp} {len(data)} bytes md5={hashlib.md5(data).hexdigest()}")

sys.exit(0 if ok else 1)
