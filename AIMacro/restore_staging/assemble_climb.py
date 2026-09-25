#!/usr/bin/env python3
import base64, zlib, pathlib, json, hashlib, sys
root = pathlib.Path(__file__).resolve().parents[2]
st = root / "AIMacro" / "restore_staging"
manifest = json.loads((st / "climb_manifest.json").read_text())
ok = True
for m in manifest:
    parts = m["parts"]
    b64 = "".join((st / p).read_text() for p in parts)
    data = zlib.decompress(base64.b64decode(b64))
    got = hashlib.md5(data).hexdigest()
    out = root / m["dest"]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    status = "OK" if got == m["md5"] else "MD5_MISMATCH"
    if got != m["md5"]:
        ok = False
    print(f"wrote {out} {len(data)} bytes md5={got} expect={m['md5']} {status}")
sys.exit(0 if ok else 1)
