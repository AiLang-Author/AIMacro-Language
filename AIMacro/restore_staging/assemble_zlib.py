#!/usr/bin/env python3
import base64, zlib, pathlib, json
root = pathlib.Path(__file__).resolve().parents[2]
st = root / "AIMacro" / "restore_staging"
# Optional: restore manifest.json from compressed staging blob
mz = st / "manifest.z.b64"
if mz.exists():
    data = zlib.decompress(base64.b64decode(mz.read_text().strip()))
    (st / "manifest.json").write_bytes(data)
    print(f"restored manifest.json {len(data)} bytes from manifest.z.b64")
manifest = json.loads((st / "manifest.json").read_text())
for m in manifest:
    b64 = "".join((st / p).read_text() for p in m["parts"])
    data = zlib.decompress(base64.b64decode(b64))
    out = root / "Librarys" / "AIMacro" / m["name"]
    out.write_bytes(data)
    print(f"wrote {out} {len(data)} bytes md5_expect={m['md5']}")
