#!/usr/bin/env python3
import base64, zlib, pathlib, json
root = pathlib.Path(__file__).resolve().parents[2]
st = root / "AIMacro" / "restore_staging"
manifest = json.loads((st / "manifest.json").read_text())
for m in manifest:
    b64 = "".join((st / p).read_text() for p in m["parts"])
    data = zlib.decompress(base64.b64decode(b64))
    out = root / "Librarys" / "AIMacro" / m["name"]
    out.write_bytes(data)
    print(f"wrote {out} {len(data)} bytes md5_expect={m['md5']}")
